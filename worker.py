from codecs import StreamReaderWriter
from typing import List, Literal, TypedDict, Optional
import os
import codecs
import ntpath
import sys
from pathlib import Path
import requests
import logging
from urllib.parse import urlparse
from time import time
from dataclasses import dataclass
from dane.base_classes import base_worker
from dane.config import cfg
from dane import Document, Task, Result
from base_util import validate_config
from asr_service import Kaldi_NL, Kaldi_NL_API, ASRService


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
logger = logging.getLogger(__name__)


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


class ParsedResult(TypedDict):
    words: str
    wordTimes: List[int]
    start: float
    sequenceNr: int
    fragmentId: str
    carrierId: str


class AsrWorker(base_worker):
    def __init__(self, config):
        logger.debug(config)

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
            self.DELETE_INPUT_ON_COMPLETION: bool = (
                config.DELETE_INPUT_ON_COMPLETION
                if "DELETE_INPUT_ON_COMPLETION" in config
                else []
            )

        except AttributeError:
            logger.exception("Missing configuration setting")
            sys.exit()

        # check if the file system is setup properly
        if not self.validate_data_dirs(self.ASR_INPUT_DIR, self.ASR_OUTPUT_DIR):
            logger.debug("ERROR: data dirs not configured properly")
            if not self.UNIT_TESTING:
                sys.exit()

        # we specify a queue name because every worker of this type should
        # listen to the same queue
        self.__queue_name = (
            "ASR"  # this is the queue that receives the work and NOT the reply queue
        )
        self.__binding_key = "#.ASR"  # ['Video.ASR', 'Sound.ASR']#'#.ASR'
        self.__depends_on = self.DANE_DEPENDENCIES

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

    def _init_asr_service(self, config, unit_test) -> ASRService:
        # now finally determine whether to use the local Kaldi or the remote API
        use_local_kaldi = "LOCAL_KALDI" in config
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
        logger.debug("determining downloader type")
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
            logger.debug(
                "{} does not exist. Make sure BASE_MOUNT_DIR exists before retrying".format(
                    i_dir.parent.absolute()
                )
            )
            return False

        # make sure the input and output dirs are there
        try:
            os.makedirs(i_dir, 0o755)
            logger.debug("created ASR input dir: {}".format(i_dir))
        except FileExistsError as e:
            logger.debug(e)

        try:
            os.makedirs(o_dir, 0o755)
            logger.debug("created ASR output dir: {}".format(o_dir))
        except FileExistsError as e:
            logger.debug(e)

        return True

    """----------------------------------INTERACTION WITH DANE SERVER ---------------------------------"""

    # DANE callback function, called whenever there is a job for this worker
    def callback(self, task: Task, doc: Document) -> CallbackResponse:
        logger.debug("receiving a task from the DANE (mock) server!")
        logger.debug(task)
        logger.debug(doc)

        # TODO check if a transcript was already generated

        # either DOWNLOAD, BG_DOWNLOAD or None (meaning the ASR worker will try to download the data itself)
        downloader_type = self.__get_downloader_type()

        # step 1 try to fetch the content via the configured DANE download worker
        download_result = (
            self.fetch_downloaded_content(doc) if downloader_type is not None else None
        )

        # try to download the file if no DANE download worker was configured
        if download_result is None:
            logger.debug(
                "The file was not downloaded by the DANE worker, downloading it myself..."
            )
            download_result = self.download_content(doc)
            if download_result is None:
                return {
                    "state": 500,
                    "message": "Could not download the document content",
                }

        input_file = download_result.file_path

        # step 3 submit the input file to the ASR service
        asr_result = self.asr_service.submit_asr_job(input_file)
        # TODO harmonize the asr_result in both work_processor and asr_service
        logger.info(asr_result)

        # step 4 generate a transcript from the ASR service's output
        if asr_result.state == 200:
            # TODO change this, harmonize the asset ID with the process ID (pid)
            asr_output_dir = self.get_asr_output_dir(self.get_asset_id(input_file))
            transcript = self.asr_output_to_transcript(asr_output_dir)
            if transcript:
                if self.cleanup_input_file(input_file, self.DELETE_INPUT_ON_COMPLETION):
                    self.save_to_dane_index(
                        doc,
                        task,
                        transcript,
                        asr_output_dir,
                        ASRProvenance(
                            asr_result.processing_time, download_result.download_time
                        ),
                    )
                    return {
                        "state": 200,
                        "message": "Successfully generated a transcript file from the ASR service output",
                    }
                else:
                    return {
                        "state": 500,
                        "message": "Generated a transcript, but could not delete the input file",
                    }
            else:
                return {
                    "state": 500,
                    "message": "Failed to generate a transcript file from the ASR service output",
                }

        # something went wrong inside the ASR service, return that response here
        return {"state": asr_result.state, "message": asr_result.message}

    def cleanup_input_file(self, input_file: str, actually_delete: bool) -> bool:
        logger.debug(f"Verifying deletion of input file: {input_file}")
        if actually_delete is False:
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
        provenance: ASRProvenance = None,
    ) -> None:
        logger.debug("saving results to DANE, task id={0}".format(task._id))
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
        logger.debug("working with this asset ID {}".format(asset_id))
        return asset_id

    def get_asr_output_dir(self, asset_id: str) -> str:
        return os.path.join(self.ASR_OUTPUT_DIR, asset_id)

    """----------------------------------DOWNLOAD FUNCTIONS ---------------------------------"""

    # https://www.openbeelden.nl/files/29/29494.29451.WEEKNUMMER243-HRE00015742.mp4
    def download_content(self, doc: Document) -> Optional[DownloadResult]:
        if not doc.target or "url" not in doc.target or not doc.target["url"]:
            logger.debug("No url found in DANE doc")
            return None

        logger.debug("downloading {}".format(doc.target["url"]))
        fn = os.path.basename(urlparse(doc.target["url"]).path)
        # fn = unquote(fn)
        # fn = doc.target['url'][doc.target['url'].rfind('/') +1:]
        output_file = os.path.join(self.ASR_INPUT_DIR, fn)
        logger.debug("saving to file {}".format(fn))

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
        logger.debug("checking download worker output")
        downloader_type = self.__get_downloader_type()
        if not downloader_type:
            logger.warning("BG_DOWNLOAD or DOWNLOAD type must be configured")
            return None

        possibles = self.handler.searchResult(doc._id, downloader_type)
        logger.info(possibles)
        # NOTE now MUST use the latest dane-beng-download-worker or dane-download-worker
        if len(possibles) > 0 and "file_path" in possibles[0]:
            return DownloadResult(
                possibles[0].get("file_path"),
                possibles[0].get("download_time", -1),
                possibles[0].get("mime_type", "unknown"),
                possibles[0].get("content_length", -1),
            )
        logger.error("No file_path found in download result")
        return None

    """----------------------------------PROCESS ASR OUTPUT (DOCKER MOUNT) --------------------------"""

    # mount/asr-output/1272-128104-0000
    def asr_output_to_transcript(
        self, asr_output_dir: str
    ) -> List[ParsedResult] | None:
        logger.debug(
            "generating a transcript from the ASR output in: {0}".format(asr_output_dir)
        )
        transcriptions = None
        if os.path.exists(asr_output_dir):
            try:
                with codecs.open(
                    os.path.join(asr_output_dir, "1Best.ctm"), encoding="utf-8"
                ) as times_file:
                    times = self.__extract_time_info(times_file)

                with codecs.open(
                    os.path.join(asr_output_dir, "1Best.txt"), encoding="utf-8"
                ) as asr_file:
                    transcriptions = self.__parse_asr_results(asr_file, times)
            except EnvironmentError as e:  # OSError or IOError...
                logger.debug(os.strerror(e.errno))

            # Clean up the extracted dir
            # shutil.rmtree(asr_output_dir)
            # logger.debug("Cleaned up folder {}".format(asr_output_dir))
        else:
            logger.debug(
                "Error: cannot generate transcript; ASR output dir does not exist"
            )

        return transcriptions

    def __parse_asr_results(
        self, asr_file: StreamReaderWriter, times: List[int]
    ) -> List[ParsedResult]:
        transcriptions = []
        i = 0
        cur_pos = 0

        for line in asr_file:
            parts = line.replace("\n", "").split("(")

            # extract the text
            words = parts[0].strip()
            num_words = len(words.split(" "))
            word_times = times[cur_pos : cur_pos + num_words]
            cur_pos = cur_pos + num_words

            # Check number of words matches the number of word_times
            if not len(word_times) == num_words:
                logger.debug(
                    "Number of words does not match word-times for file: {}, "
                    "current position in file: {}".format(asr_file.name, cur_pos)
                )

            # extract the carrier and fragment ID
            carrier_fragid = parts[1].split(" ")[0].split(".")
            carrier = carrier_fragid[0]
            fragid = carrier_fragid[1]

            # extract the starttime
            sTime = parts[1].split(" ")[1].replace(")", "").split(".")
            starttime = int(sTime[0]) * 1000

            subtitle: ParsedResult = {
                "words": words,
                "wordTimes": word_times,
                "start": float(starttime),
                "sequenceNr": i,
                "fragmentId": fragid,
                "carrierId": carrier,
            }
            transcriptions.append(subtitle)
            i += 1
        return transcriptions

    def __extract_time_info(self, times_file: StreamReaderWriter) -> List[int]:
        times = []

        for line in times_file:
            time_string = line.split(" ")[2]
            ms_value = int(float(time_string) * 1000)
            times.append(ms_value)

        return times


# Start the worker
if __name__ == "__main__":
    w = AsrWorker(cfg)
    try:
        w.run()
    except (KeyboardInterrupt, SystemExit):
        w.stop()
