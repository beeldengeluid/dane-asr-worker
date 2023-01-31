import os
import tarfile
import glob
import json
import sys
import logging
import ntpath
from api_util import APIResponse
import base_util
from transcode import transcode_to_mp3, get_transcode_output_path
import requests
from requests.exceptions import ConnectionError
from time import time, sleep
from dataclasses import dataclass
from abc import ABC, abstractmethod


"""
This module contains functions for running audio files through Kaldi_NL to generate a speech transcript.

Moreover this module has functions for:
- validating the ASR output
- generating a JSON file (based on the 1Best.ctm transcript file)
- packaging the ASR output (as a tar)

"""
ASR_TRANSCRIPT_FILE = "1Best.ctm"
logger = logging.getLogger(__name__)


# returned by submit_asr_job()
@dataclass
class AsrResult:
    state: int
    message: str
    processing_time: float


def to_asr_result(api_response: APIResponse, processing_time: float = -1) -> AsrResult:
    return AsrResult(
        api_response.value["state"],
        api_response.value["message"],
        processing_time,
    )


class ASRService(ABC):
    def __init__(self, config, unit_test):
        self.config = config
        # enforce config validation
        if not self._validate_config():
            logger.critical("Malconfigured, quitting...")
            sys.exit()

    @abstractmethod
    def _validate_config(self) -> bool:
        raise NotImplementedError("Implement to validate the config")

    @abstractmethod
    def submit_asr_job(self, input_file: str) -> AsrResult:
        raise NotImplementedError("Implement to export results")


class Kaldi_NL(ASRService):
    def __init__(self, config, unit_test):
        super().__init__(config, unit_test)
        self.KALDI_NL_DIR = config.LOCAL_KALDI.KALDI_NL_DIR
        self.KALDI_NL_DECODER = config.LOCAL_KALDI.KALDI_NL_DECODER
        self.KALDI_NL_MODEL_FETCHER: str = config.LOCAL_KALDI.KALDI_NL_MODEL_FETCHER
        self.KALDI_NL_MODEL_DIR: str = (
            config.LOCAL_KALDI.KALDI_NL_MODEL_DIR
        )  # NOTE: present in config, but not used...
        self.ASR_WORD_JSON_FILE = config.LOCAL_KALDI.ASR_WORD_JSON_FILE
        self.ASR_PACKAGE_NAME = config.LOCAL_KALDI.ASR_PACKAGE_NAME

        self.ASR_OUTPUT_DIR = os.path.join(
            config.FILE_SYSTEM.BASE_MOUNT, config.FILE_SYSTEM.OUTPUT_DIR
        )

        # make sure the language models are downloaded
        if not self._check_language_models(
            self.KALDI_NL_DIR, self.KALDI_NL_MODEL_FETCHER
        ):
            logger.error(
                "Could not properly download required language models, quitting..."
            )
            sys.exit()

    def _validate_config(self) -> bool:
        try:
            assert (
                "LOCAL_KALDI" in self.config
            ), "LOCAL_KALDI section not in self.config"
            assert base_util.check_setting(
                self.config.LOCAL_KALDI.ASR_PACKAGE_NAME, str
            ), "LOCAL_KALDI.ASR_PACKAGE_NAME"
            assert base_util.check_setting(
                self.config.LOCAL_KALDI.ASR_WORD_JSON_FILE, str
            ), "LOCAL_KALDI.ASR_WORD_JSON_FILE"
            assert base_util.check_setting(
                self.config.LOCAL_KALDI.KALDI_NL_DIR, str
            ), "LOCAL_KALDI.KALDI_NL_DIR"
            assert base_util.check_setting(
                self.config.LOCAL_KALDI.KALDI_NL_DECODER, str
            ), "LOCAL_KALDI.KALDI_NL_DECODER"
            assert base_util.check_setting(
                self.config.LOCAL_KALDI.KALDI_NL_MODEL_DIR, str, True
            ), "LOCAL_KALDI.KALDI_NL_MODEL_DIR"
            assert base_util.check_setting(
                self.config.LOCAL_KALDI.KALDI_NL_MODEL_FETCHER, str
            ), "LOCAL_KALDI.KALDI_NL_MODEL_FETCHER"
        except AssertionError as e:
            logger.critical(f"Configuration error: {str(e)}")
            return False
        return True

    def _check_language_models(self, kaldi_nl_dir: str, kaldi_nl_model_fetcher: str):
        logger.info("Checking availability of language models; will download if absent")
        cmd = f"cd {kaldi_nl_dir} && ./{kaldi_nl_model_fetcher}"
        return base_util.run_shell_command(cmd)

    # processes the input and keeps a PID file with status information in asynchronous mode
    def submit_asr_job(self, input_file_path) -> AsrResult:
        logger.info(f"Processing ASR for {input_file_path}")

        if not os.path.isfile(input_file_path):  # check if inputfile exists
            logger.error("ASR input file does not exist")
            return to_asr_result(APIResponse.FILE_NOT_FOUND)

        # extract the asset_id, i.e. filename without the path, and the file extension
        asset_id, extension = self._get_asset_info(input_file_path)
        logger.info(
            f"determined asset_id: {asset_id}, extension: {extension} from input_file_path: {input_file_path}"
        )

        # check if the file needs to be transcoded and possibly obtain a new asr_input_path
        try:
            asr_input_path = self._try_transcode(input_file_path, asset_id, extension)
        except ValueError as e:
            logger.exception("transcode failed")
            return to_asr_result(APIResponse[str(e)])

        # NOTE: record processing time for ASR only for now
        start_time = time()
        # run the ASR
        api_response = self._run_asr(asr_input_path, asset_id)
        logger.info(api_response)
        return to_asr_result(api_response, time() - start_time)

    def _try_transcode(self, asr_input_path, asset_id, extension):
        logger.info(
            f"Determining if transcode is required for asr_input_path: {asr_input_path} asset_id: ({asset_id}) extension: ({extension})"
        )
        if not self._is_audio_file(extension):
            if not self._is_transcodable(extension):
                logger.error(f"input with extension {extension} is not transcodable")
                raise ValueError(APIResponse.ASR_INPUT_UNACCEPTABLE.name)

            logger.info(
                f"calling get_transcode_output_path with asr_input_path: {asr_input_path}, asset_id: {asset_id}"
            )
            transcoding_output_path = get_transcode_output_path(
                asr_input_path, asset_id
            )

            success = transcode_to_mp3(
                asr_input_path,
                transcoding_output_path,
            )
            if success is False:
                logger.error("Transcode failed")
                raise ValueError(APIResponse.TRANSCODE_FAILED.name)

            logger.info(
                f"Transcode of {extension} successful, returning: {transcoding_output_path}"
            )
            return (
                transcoding_output_path  # the transcode output is the input for the ASR
            )
        logger.info(
            f"No transcode was necessary, returning original input: {asr_input_path}"
        )
        return asr_input_path

    def _get_asset_info(self, file_path):
        # grab the file_name from the path
        file_name = ntpath.basename(file_path)

        # split up the file in asset_id (used for creating a subfolder in the output) and extension
        asset_id, extension = os.path.splitext(file_name)

        return asset_id, extension

    def _is_audio_file(self, extension):
        return extension in [".mp3", ".wav"]

    def _is_transcodable(self, extension):
        return extension in [".mov", ".mp4", ".m4a", ".3gp", ".3g2", ".mj2"]

    # runs the asr on the input path and puts the results in the ASR_OUTPUT_DIR dir
    def _run_asr(self, input_path, asset_id) -> APIResponse:
        logger.info(f"Starting ASR on {input_path}")
        cmd = 'cd {}; ./{} "{}" "{}/{}"'.format(
            self.KALDI_NL_DIR,
            self.KALDI_NL_DECODER,
            input_path,
            self.ASR_OUTPUT_DIR,
            asset_id,
        )
        try:
            base_util.run_shell_command(cmd)
        except Exception:
            logger.exception("Kaldi command failed")
            return APIResponse.ASR_FAILED

        # finally process the ASR results and return the status message
        return self._process_asr_output(asset_id)

    def _process_asr_output(self, asset_id) -> APIResponse:
        logger.info("processing the output of {}".format(asset_id))

        if self._validate_asr_output(asset_id) is False:
            logger.error("ASR output is corrupt")
            return APIResponse.ASR_OUTPUT_CORRUPT

        # create a word.json file
        self._create_word_json(asset_id, True)

        # package the output
        self._package_output(asset_id)

        # package the features and json file, so it can be used for indexing or something else
        return APIResponse.ASR_SUCCESS

    # if there is no 1Best.ctm there is something wrong with the input file or Kaldi...
    # TODO also check if the files and dir for _package_output are there
    def _validate_asr_output(self, asset_id):
        transcript_file = self.__get_transcript_file_path(asset_id)
        logger.info(f"Checking if transcript exists: {transcript_file}")
        return os.path.isfile(transcript_file)

    # packages the features and the human readable output (1Best.*)
    def _package_output(self, asset_id):
        logger.info(f"Packaging output for asset ID: {asset_id}")
        output_dir = self._get_output_dir(asset_id)
        files_to_be_added = [
            "/{0}/liumlog/*.seg".format(output_dir),
            "/{0}/1Best.*".format(output_dir),
            "/{0}/intermediate/decode/*".format(output_dir),
        ]

        # also add the words json file if it was generated
        if os.path.exists(self.__get_words_file_path(asset_id)):
            logger.info("Adding words JSON file to ASR package")
            files_to_be_added.append(self.__get_words_file_path(asset_id))

        tar_path = os.path.join(os.sep, output_dir, self.ASR_PACKAGE_NAME)
        tar = tarfile.open(tar_path, "w:gz")

        for pattern in files_to_be_added:
            for file_path in glob.glob(pattern):
                path, asset_id = os.path.split(file_path)
                tar.add(file_path, arcname=asset_id)

        tar.close()

    def _create_word_json(self, asset_id, save_in_asr_output=False):
        logger.info("Creating word JSON")
        transcript = self.__get_transcript_file_path(asset_id)
        word_json = []
        with open(transcript, encoding="utf-8", mode="r") as file:
            for line in file.readlines():
                logger.debug(line)
                data = line.split(" ")

                start_time = float(data[2]) * 1000  # in millisec
                mark = data[4]
                json_entry = {"start": start_time, "words": mark}
                word_json.append(json_entry)

        if save_in_asr_output:
            with open(self.__get_words_file_path(asset_id), "w+") as outfile:
                json.dump(word_json, outfile, indent=4)

        logger.debug(json.dumps(word_json, indent=4, sort_keys=True))
        return word_json

    def _get_output_dir(self, asset_id):
        return os.path.join(os.sep, self.ASR_OUTPUT_DIR, asset_id)

    def __get_transcript_file_path(self, asset_id):
        return os.path.join(os.sep, self._get_output_dir(asset_id), ASR_TRANSCRIPT_FILE)

    def __get_words_file_path(self, asset_id):
        return os.path.join(
            os.sep, self._get_output_dir(asset_id), self.ASR_WORD_JSON_FILE
        )


class Kaldi_NL_API(ASRService):
    def __init__(self, config, unit_test):
        super().__init__(config, unit_test)
        self.ASR_API_HOST: str = config.ASR_API.HOST
        self.ASR_API_PORT: int = config.ASR_API.PORT
        self.ASR_API_WAIT_FOR_COMPLETION: bool = config.ASR_API.WAIT_FOR_COMPLETION
        self.ASR_API_SIMULATE: bool = config.ASR_API.SIMULATE

        # wait for the ASR_API to be up
        if not self._wait_for_asr_service():
            sys.exit()

    def _validate_config(self) -> bool:
        try:
            assert "ASR_API" in self.config, "ASR_API section not in self.config"
            assert base_util.check_setting(
                self.config.ASR_API.HOST, str
            ), "ASR_API.HOST"
            assert base_util.check_setting(
                self.config.ASR_API.PORT, int
            ), "ASR_API.PORT"
            assert base_util.check_setting(
                self.config.ASR_API.WAIT_FOR_COMPLETION, bool
            ), "ASR_API.WAIT_FOR_COMPLETION"
            assert base_util.check_setting(
                self.config.ASR_API.SIMULATE, bool
            ), "ASR_API.SIMULATE"
        except AssertionError as e:
            logger.critical(f"Configuration error: {str(e)}")
            return False
        return True

    # make sure the service is ready before letting the server know that this worker is ready
    def _wait_for_asr_service(self, attempts: int = 0) -> bool:
        url = "http://{}:{}/ping".format(self.ASR_API_HOST, self.ASR_API_PORT)
        try:
            resp = requests.get(url)
            logger.info(resp.status_code)
            logger.info(resp.text)
            if resp.status_code == 200 and resp.text == "pong":
                return True
        except ConnectionError:
            logger.critical("Cannot connect to ASR service at all, not retrying")
            return False
        if attempts < 100:  # TODO add to configuration
            sleep(2)
            self._wait_for_asr_service(attempts + 1)

        logger.critical(
            "Error: after 100 attempts the ASR service is still not ready! Stopping worker"
        )
        return False

    def submit_asr_job(self, input_file: str) -> AsrResult:
        input_hash = base_util.hash_string(input_file)
        logger.info(
            "Going to submit {} to the ASR service, using PID={}".format(
                input_file, input_hash
            )
        )
        start_time = time()  # record just before calling the ASR service
        try:
            dane_asr_api_url = "http://{}:{}/api/{}/{}?input_file={}&wait_for_completion={}&simulate={}".format(
                self.ASR_API_HOST,
                self.ASR_API_PORT,
                "process",  # replace with process_debug to debug(?)
                input_hash,
                input_file,
                "1" if self.ASR_API_WAIT_FOR_COMPLETION else "0",
                "1" if self.ASR_API_SIMULATE else "0",
            )
            logger.info(dane_asr_api_url)
            resp = requests.put(dane_asr_api_url)

            # return the result right away if in synchronous mode
            if self.ASR_API_WAIT_FOR_COMPLETION:
                return self._parse_asr_service_response(resp, start_time)
            else:  # poll the ASR service (async mode)
                return self._poll_asr_service(input_file, input_hash, start_time)
        except requests.exceptions.ConnectionError:
            logger.exception("Could not connect to ASR service")
            return AsrResult(
                500,
                "Failure: could not connect to the ASR service",
                time() - start_time,
            )

    def _parse_asr_service_response(
        self, resp: requests.Response, start_time: float
    ) -> AsrResult:
        if resp.status_code == 200:
            logger.info("The ASR service is done, returning the results")
            try:
                data = json.loads(resp.text)
                return AsrResult(
                    data["state"],
                    data["message"],
                    time() - start_time,  # processing_time
                )  # NOTE see dane-kaldi-nl-api for the returned data
            except json.JSONDecodeError:
                logger.exception("ASR service returned invalid JSON")
            except KeyError:
                logger.exception("ASR service JSON did not contain expected data")

        logger.error("ASR service did not return success")
        logger.info(resp.text)
        return AsrResult(
            500,
            f"Failure: the ASR service returned status_code {resp.status_code}",
            time() - start_time,
        )

    # Polls the ASR service, using the input_hash for PID reference (TODO synch with asset_id)
    def _poll_asr_service(
        self, input_file: str, input_hash: str, start_time: float
    ) -> AsrResult:
        logger.info("Polling the ASR service to check when it is finished")
        while True:
            logger.info("Polling the ASR service to wait for completion")
            try:
                resp = requests.get(
                    "http://{0}:{1}/api/{2}/{3}".format(
                        self.ASR_API_HOST,
                        self.ASR_API_PORT,
                        "process",
                        input_hash,
                    )
                )
                process_msg = json.loads(resp.text)
                state = process_msg.get("state", 500)
                finished = process_msg.get("finished", False)
                if finished:
                    return AsrResult(
                        200,
                        f"The ASR service generated valid output for: {input_file}",
                        time() - start_time,
                    )
                elif state == 500:
                    return AsrResult(
                        500,
                        f"The ASR failed to produce the desired output for: {input_file}",
                        time() - start_time,
                    )
                elif state == 404:
                    return AsrResult(
                        404,
                        f"The ASR failed to find the input file {input_file}",
                        time() - start_time,
                    )
            except requests.exceptions.ConnectionError:
                logger.exception("Could not connect to ASR service (polling)")
                break
            except json.JSONDecodeError:
                logger.exception("Could not connect to ASR service (polling)")
                break

            # wait for ten seconds before polling again
            sleep(10)
        return AsrResult(
            500,
            f"The ASR failed to produce the desired output {input_file}",
            time() - start_time,
        )
