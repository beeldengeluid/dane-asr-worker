import logging
import os
import sys
from pika.exceptions import ChannelClosedByBroker
from typing import List, Optional

from dane.base_classes import base_worker
from dane import Document, Task, Result

from asr_service import Kaldi_NL
from base_util import validate_config, LOG_FORMAT
from io_util import (
    validate_data_dirs,
    fetch_input_file,
    cleanup_input_file,
    get_asr_output_dir,
    get_asset_id,
)
from models import CallbackResponse, ASRProvenance
from transcript import (
    ParsedResult,
    generate_transcript,
    delete_asr_output,
    transfer_asr_output,
)


# initialises the root logger
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,  # configure a stream handler only for now (single handler)
    format=LOG_FORMAT,
)
logger = logging.getLogger()


class AsrWorker(base_worker):
    def __init__(self, config):
        logger.info(config)

        self.UNIT_TESTING = os.getenv("DW_ASR_UNIT_TESTING", False)

        if not validate_config(config, not self.UNIT_TESTING):
            logger.error("Invalid config, quitting")
            sys.exit()

        # first make sure the config has everything we need
        # Note: base_config is loaded first by DANE, so make sure you overwrite everything in your config.yml!
        try:
            # put all of the relevant settings in a variable
            self.BASE_MOUNT: str = config.FILE_SYSTEM.BASE_MOUNT

            # construct the input & output paths using the base mount as a parent dir
            self.ASR_INPUT_DIR: str = os.path.join(
                self.BASE_MOUNT, config.FILE_SYSTEM.INPUT_DIR
            )
            self.ASR_OUTPUT_DIR: str = os.path.join(
                self.BASE_MOUNT, config.FILE_SYSTEM.OUTPUT_DIR
            )

            self.DANE_DEPENDENCIES: list = (
                config.DANE_DEPENDENCIES if "DANE_DEPENDENCIES" in config else []
            )

            # read from default DANE settings
            self.DELETE_INPUT_ON_COMPLETION: bool = config.INPUT.DELETE_ON_COMPLETION
            self.DELETE_OUTPUT_ON_COMPLETION: bool = config.OUTPUT.DELETE_ON_COMPLETION
            self.TRANSFER_OUTPUT_ON_COMPLETION: bool = (
                config.OUTPUT.TRANSFER_ON_COMPLETION
            )

        except AttributeError:
            logger.exception("Missing configuration setting")
            sys.exit()

        # check if the file system is setup properly
        if not validate_data_dirs(self.ASR_INPUT_DIR, self.ASR_OUTPUT_DIR):
            logger.info("ERROR: data dirs not configured properly")
            if not self.UNIT_TESTING:
                sys.exit()

        # we specify a queue name because every worker of this type should
        # listen to the same queue
        self.__queue_name = (
            "ASR"  # this is the queue that receives the work and NOT the reply queue
        )
        self.__binding_key = "#.ASR"  # ['Video.ASR', 'Sound.ASR']#'#.ASR'
        # DOWNLOAD or None
        self.__depends_on = (
            config.DANE_DEPENDENCIES if "DANE_DEPENDENCIES" in config else []
        )

        if not self.UNIT_TESTING:
            self.asr_service = Kaldi_NL(config, self.UNIT_TESTING)

        super().__init__(
            self.__queue_name,
            self.__binding_key,
            config,
            self.__depends_on,
            auto_connect=not self.UNIT_TESTING,
            no_api=self.UNIT_TESTING,
        )

        # NOTE: cannot be automaticcally filled, because no git client is present
        if not self.generator:
            logger.info("Generator was None, creating it now")
            self.generator = {
                "id": "dane-asr-worker",
                "type": "Software",
                "name": "ASR",
                "homepage": "https://github.com/beeldengeluid/dane-asr-worker",
            }

    """----------------------------------INTERACTION WITH DANE SERVER ---------------------------------"""

    # DANE callback function, called whenever there is a job for this worker
    def callback(self, task: Task, doc: Document) -> CallbackResponse:
        logger.info("Receiving a task from the DANE (mock) server!")
        logger.info(task)
        logger.info(doc)

        # TODO check if a transcript was already generated

        # step 1: try to fetch the content via the configured DANE download worker
        download_result = fetch_input_file(doc, self.ASR_INPUT_DIR, self.handler)
        if download_result is None:
            logger.error("Could not obtain input file")
            return self.finalize_callback(
                500, "Could not download the document content"
            )

        input_file = download_result.file_path

        # step 3: submit the input file to the ASR service
        asr_result = self.asr_service.submit_asr_job(input_file)
        # TODO harmonize the asr_result in both work_processor and asr_service
        logger.info(asr_result)

        # step 4: generate a transcript from the ASR service's output
        if asr_result.state != 200:
            logger.error("Something went wrong in the ASR service")
            # something went wrong inside the ASR service, return that response here
            return self.finalize_callback(
                asr_result.state, asr_result.message, input_file
            )

        # step 5: ASR returned successfully, generate the transcript
        asset_id = get_asset_id(input_file)
        asr_output_dir = get_asr_output_dir(self.ASR_OUTPUT_DIR, asset_id)
        transcript = generate_transcript(asr_output_dir)

        #
        if not transcript:
            logger.error(
                "Failed to generate a transcript file from the ASR service output"
            )
            return self.finalize_callback(
                500,
                "Failed to generate a transcript file from the ASR service output",
                input_file,
                asr_output_dir,
            )

        # step 6: transfer the output to S3 (if configured so)
        transfer_success = True
        if self.TRANSFER_OUTPUT_ON_COMPLETION:
            transfer_success = transfer_asr_output(asr_output_dir, asset_id)

        if (
            not transfer_success
        ):  # failure of transfer, impedes the workflow, so return error
            return self.finalize_callback(
                500, "Failed to transfer output to S3", input_file, asr_output_dir
            )

        # step 7: save the results back to the DANE index
        self.save_to_dane_index(
            doc,
            task,
            transcript,
            asr_output_dir,
            ASRProvenance(asr_result.processing_time, download_result.download_time),
        )
        return self.finalize_callback(
            200,
            "Successfully generated a transcript file from the ASR service output",
            input_file,
            asr_output_dir,
        )

    # regardless of success or failure, try to cleanup the input/output properly for every callback
    def finalize_callback(
        self,
        state: int,
        msg: str,
        input_file: Optional[str] = None,
        asr_output_dir: Optional[str] = None,
    ) -> CallbackResponse:
        cleanup_msg = ""

        # step 1: clean the input file (if configured so)
        if input_file:
            if not cleanup_input_file(
                self.ASR_INPUT_DIR, input_file, self.DELETE_INPUT_ON_COMPLETION
            ):
                logger.warning(
                    f"Generated a transcript, but could not delete input: {input_file}"
                )
                cleanup_msg += "; failed to delete input file"

        # step 2: clear the output files (if configured so)
        if asr_output_dir:
            delete_success = True
            if self.DELETE_OUTPUT_ON_COMPLETION:
                delete_success = delete_asr_output(asr_output_dir)
            if (
                not delete_success
            ):  # NOTE: just a warning for now, but one to keep an EYE out for
                logger.warning(f"Could not delete output files: {asr_output_dir}")
                cleanup_msg += "; failed to delete output files"
        return {"state": state, "message": msg + cleanup_msg}

    # Note: the supplied transcript is EXACTLY the same as what we use in layer__asr in the collection indices,
    # meaning it should be quite trivial to append the DANE output into a collection
    def save_to_dane_index(
        self,
        doc: Document,
        task: Task,
        transcript: List[ParsedResult],
        asr_output_dir: str,
        provenance: Optional[ASRProvenance] = None,
    ) -> None:
        logger.info("saving results to DANE, task id={0}".format(task._id))
        # TODO figure out the multiple lines per transcript (refresh my memory)
        r = Result(
            self.generator,
            payload={
                "transcript": transcript,
                "asr_output_dir": asr_output_dir,
                "doc_id": doc._id,
                "task_id": task._id if task else None,  # TODO add this as well
                "doc_target_id": doc.target["id"],
                "doc_target_url": doc.target["url"],
                "provenance": provenance.to_json()
                if provenance
                else None,  # TODO test this
            },
            api=self.handler,
        )
        r.save(task._id)


# Start the worker
if __name__ == "__main__":
    from dane.config import cfg

    w = AsrWorker(cfg)
    try:
        w.run()
    except ChannelClosedByBroker:
        """
        (406, 'PRECONDITION_FAILED - delivery acknowledgement on channel 1 timed out.
        Timeout value used: 1800000 ms.
        This timeout value can be configured, see consumers doc guide to learn more')
        """
        logger.critical("Please increase the consumer_timeout in your RabbitMQ server")
        w.stop()
    except (KeyboardInterrupt, SystemExit):
        w.stop()
