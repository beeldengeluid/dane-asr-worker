from typing import List, Literal, TypedDict, Optional
import os
import ntpath
import sys
from pathlib import Path
import requests
import logging
from urllib.parse import urlparse
from time import time
from dataclasses import dataclass
from dane.base_classes import base_worker
from dane import Document, Task, Result
from transcript import (
    ParsedResult,
    generate_transcript,
    delete_asr_output,
    transfer_asr_output,
)
from base_util import validate_config, LOG_FORMAT
from asr_service import Kaldi_NL, Kaldi_NL_API, ASRService
from pika.exceptions import ChannelClosedByBroker

"""
This class implements a DANE worker and thus serves as the process receiving tasks from DANE

This particular worker only picks up work from the ASR queue and only will go ahead with (ASR) processing
audiovisual input.

The input file is obtained by requesting the file path from the document index. This file path SHOULD have been
made available by the download worker (before the task was received in this worker)
"""


"""
TODO now the output dir created by by DANE (createDirs()) for the PATHS.OUT_FOLDER is not used:

- /mnt/dane-fs/output-files/03/d2/8a/03d28a03643a981284b403b91b95f6048576c234

Instead we put the ASR in:

- /mnt/dane-fs/output-files/asr-output/{asset-id}
"""
# initialises the root logger
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,  # configure a stream handler only for now (single handler)
    format=LOG_FORMAT,
)
logger = logging.getLogger()


# TODO get version from Kaldi CLI
@dataclass
class ASRProvenance:
    asr_processing_time: float  # retrieved via submit_asr_job()
    download_time: float  # retrieved via dane-beng-download-worker or download_content()
    kaldi_nl_version: str = "Kaldi-NL v0.4.1"  # default for now
    kaldi_nl_git_url: str = (
        "https://github.com/opensource-spraakherkenning-nl/Kaldi_NL"  # default for now
    )

    def to_json(self):
        return {
            "asr_processing_time": self.asr_processing_time,
            "download_time": self.download_time,
            "kaldi_nl_version": self.kaldi_nl_version,
            "kaldi_nl_git_url": self.kaldi_nl_git_url,
        }


# NOTE copied from dane-beng-download-worker (move this to DANE later)
@dataclass
class DownloadResult:
    file_path: str  # target_file_path,  # TODO harmonize with dane-download-worker
    download_time: float = -1  # time (secs) taken to receive data after request
    mime_type: str = "unknown"  # download_data.get("mime_type", "unknown"),
    content_length: int = -1  # download_data.get("content_length", -1),


# returned by callback()
class CallbackResponse(TypedDict):
    state: int
    message: str


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
        if not self.validate_data_dirs(self.ASR_INPUT_DIR, self.ASR_OUTPUT_DIR):
            logger.info("ERROR: data dirs not configured properly")
            if not self.UNIT_TESTING:
                sys.exit()

        # we specify a queue name because every worker of this type should
        # listen to the same queue
        self.__queue_name = (
            "ASR"  # this is the queue that receives the work and NOT the reply queue
        )
        self.__binding_key = "#.ASR"  # ['Video.ASR', 'Sound.ASR']#'#.ASR'
        self.__depends_on = self.DANE_DEPENDENCIES  # TODO make this part of DANE lib?

        if not self.UNIT_TESTING:
            self.asr_service = self._init_asr_service(
                config, self.UNIT_TESTING
            )  # init below

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

    # Determine whether to use the local Kaldi_NL or the remote Kaldi_NL API
    def _init_asr_service(self, config, unit_test) -> ASRService:
        use_local_kaldi = "LOCAL_KALDI" in config  # local kaldi takes precedence
        if not use_local_kaldi:
            if "ASR_API" not in config:
                logger.critical("No ASR_API or LOCAL_KALDI configured: quitting...")
                sys.exit()

        if use_local_kaldi:  # TODO check if local kaldi is available
            logger.info("Going ahead with the local Kaldi_NL client")
            return Kaldi_NL(config, unit_test)  # init local Kaldi_NL client
        else:  # connect to the Kaldi_NL API
            logger.info("Going ahead with the Kaldi_NL API")
            return Kaldi_NL_API(config, unit_test)  # init the Kaldi_NL API

    def __get_downloader_type(self) -> Literal["DOWNLOAD", "BG_DOWNLOAD"] | None:
        logger.info("determining downloader type")
        if "DOWNLOAD" in self.DANE_DEPENDENCIES:
            return "DOWNLOAD"
        elif "BG_DOWNLOAD" in self.DANE_DEPENDENCIES:
            return "BG_DOWNLOAD"
        logger.warning(
            "Warning: did not find DOWNLOAD or BG_DOWNLOAD in worker dependencies"
        )
        return None

    """----------------------------------INIT VALIDATION FUNCTIONS ---------------------------------"""

    def validate_data_dirs(self, asr_input_dir: str, asr_output_dir: str) -> bool:
        i_dir = Path(asr_input_dir)
        o_dir = Path(asr_output_dir)

        if not os.path.exists(i_dir.parent.absolute()):
            logger.info(
                "{} does not exist. Make sure BASE_MOUNT_DIR exists before retrying".format(
                    i_dir.parent.absolute()
                )
            )
            return False

        # make sure the input and output dirs are there
        try:
            os.makedirs(i_dir, 0o755)
            logger.info("created ASR input dir: {}".format(i_dir))
        except FileExistsError as e:
            logger.info(e)

        try:
            os.makedirs(o_dir, 0o755)
            logger.info("created ASR output dir: {}".format(o_dir))
        except FileExistsError as e:
            logger.info(e)

        return True

    """----------------------------------INTERACTION WITH DANE SERVER ---------------------------------"""

    # DANE callback function, called whenever there is a job for this worker
    def callback(self, task: Task, doc: Document) -> CallbackResponse:
        logger.info("Receiving a task from the DANE (mock) server!")
        logger.info(task)
        logger.info(doc)

        # TODO check if a transcript was already generated

        # either DOWNLOAD, BG_DOWNLOAD or None (meaning the ASR worker will try to download the data itself)
        downloader_type = self.__get_downloader_type()

        # step 1: try to fetch the content via the configured DANE download worker
        download_result = (
            self.fetch_downloaded_content(doc) if downloader_type is not None else None
        )

        # step 2: try to download the file if no DANE download worker was configured
        if download_result is None:
            logger.info(
                "The file was not downloaded by the DANE worker, downloading it myself..."
            )
            download_result = self.download_content(doc)
            if download_result is None:
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
            # something went wrong inside the ASR service, return that response here
            return self.finalize_callback(
                asr_result.state, asr_result.message, input_file
            )

        # step 5: ASR returned successfully, generate the transcript
        asset_id = self.get_asset_id(input_file)
        asr_output_dir = self.get_asr_output_dir(asset_id)
        transcript = generate_transcript(asr_output_dir)

        #
        if not transcript:
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
            if not self.cleanup_input_file(input_file, self.DELETE_INPUT_ON_COMPLETION):
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

    # TODO move this to DANE library as it is quite generic (DELETE_INPUT_ON_COMPLETION param as well)
    def cleanup_input_file(self, input_file: str, actually_delete: bool) -> bool:
        logger.info(f"Verifying deletion of input file: {input_file}")
        if actually_delete is False:
            logger.info("Configured to leave the input alone, skipping deletion")
            return True

        # first remove the input file
        try:
            os.remove(input_file)
            logger.info(f"Deleted ASR input file: {input_file}")
            # also remove the transcoded mp3 file (if any)
            if input_file.find(".mp3") == -1 and input_file.find(".") != -1:
                mp3_input_file = f"{input_file[:input_file.rfind('.')]}.mp3"
                if os.path.exists(mp3_input_file):
                    os.remove(mp3_input_file)
                    logger.info(f"Deleted mp3 transcode file: {mp3_input_file}")
        except OSError:
            logger.exception("Could not delete input file")
            return False

        # now remove the "chunked path" from /mnt/dane-fs/input-files/03/d2/8a/03d28a03643a981284b403b91b95f6048576c234/xyz.mp4
        try:
            os.chdir(self.ASR_INPUT_DIR)  # cd /mnt/dane-fs/input-files
            os.removedirs(
                f".{input_file[len(self.ASR_INPUT_DIR):input_file.rfind(os.sep)]}"
            )  # /03/d2/8a/03d28a03643a981284b403b91b95f6048576c234
            logger.info("Deleted empty input dirs too")
        except OSError:
            logger.exception("OSError while removing empty input file dirs")
        except FileNotFoundError:
            logger.exception("FileNotFoundError while removing empty input file dirs")

        return True  # return True even if empty dirs were not removed

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

    """----------------------------------ID MANAGEMENT FUNCTIONS ---------------------------------"""

    # the file name without extension is used as an asset ID by the ASR container to save the results
    def get_asset_id(self, input_file: str) -> str:
        # grab the file_name from the path
        file_name = ntpath.basename(input_file)

        # split up the file in asset_id (used for creating a subfolder in the output) and extension
        asset_id, extension = os.path.splitext(file_name)
        logger.info("working with this asset ID {}".format(asset_id))
        return asset_id

    def get_asr_output_dir(self, asset_id: str) -> str:
        return os.path.join(self.ASR_OUTPUT_DIR, asset_id)

    """----------------------------------DOWNLOAD FUNCTIONS ---------------------------------"""

    # https://www.openbeelden.nl/files/29/29494.29451.WEEKNUMMER243-HRE00015742.mp4
    def download_content(self, doc: Document) -> Optional[DownloadResult]:
        if not doc.target or "url" not in doc.target or not doc.target["url"]:
            logger.info("No url found in DANE doc")
            return None

        logger.info("downloading {}".format(doc.target["url"]))
        fn = os.path.basename(urlparse(doc.target["url"]).path)
        # fn = unquote(fn)
        # fn = doc.target['url'][doc.target['url'].rfind('/') +1:]
        output_file = os.path.join(self.ASR_INPUT_DIR, fn)
        logger.info("saving to file {}".format(fn))

        # download if the file is not present (preventing unnecessary downloads)
        start_time = time()
        if not os.path.exists(output_file):
            with open(output_file, "wb") as file:
                response = requests.get(doc.target["url"])
                file.write(response.content)
                file.close()
        download_time = time() - start_time
        return DownloadResult(
            fn,  # NOTE or output_file? hmmm
            download_time,  # TODO add mime_type and content_length
        )

    def fetch_downloaded_content(self, doc: Document) -> Optional[DownloadResult]:
        logger.info("checking download worker output")
        downloader_type = self.__get_downloader_type()
        if not downloader_type:
            logger.warning("BG_DOWNLOAD or DOWNLOAD type must be configured")
            return None

        possibles = self.handler.searchResult(doc._id, downloader_type)
        logger.info(possibles)
        # NOTE now MUST use the latest dane-beng-download-worker or dane-download-worker
        if len(possibles) > 0 and "file_path" in possibles[0].payload:
            return DownloadResult(
                possibles[0].payload.get("file_path"),
                possibles[0].payload.get("download_time", -1),
                possibles[0].payload.get("mime_type", "unknown"),
                possibles[0].payload.get("content_length", -1),
            )
        logger.error("No file_path found in download result")
        return None


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
