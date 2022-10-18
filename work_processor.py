import os
import ntpath
import shutil
import logging
from api_util import APIResponse
from asr import ASR
from transcode import get_transcode_output_path, transcode_to_mp3
import base_util


"""
This module contains all the specific processing functions for the DANE-asr-worker. The reason
to separate it from worker.py is so it can also be called via the server.py (debugging UI)

The processing consists of:
- validating the input file (provided by the download worker)
- if it is an audio file: simply run ASR (see module: asr.py)
- if not: first transcode it (see module: transcode.py)
- finally: package the ASR output into a tar.gz (optional)
"""
logger = logging.getLogger(__name__)


class WorkProcessor(object):
    def __init__(self, config):
        self.asr = ASR(config)

    def check_language_models(self, config):
        logger.debug(
            "Checking availability of language models; will download if absent"
        )
        cmd = f"cd {config['KALDI_NL_DIR']} && ./{config['KALDI_NL_MODEL_FETCHER']}"
        return base_util.run_shell_command(cmd, logger)

    # processes the input and keeps a PID file with status information in asynchronous mode
    def process_input_file(self, input_file_path) -> APIResponse:
        logger.debug(f"processing {input_file_path}")

        if not os.path.isfile(input_file_path):  # check if inputfile exists
            return APIResponse.FILE_NOT_FOUND

        # extract the asset_id, i.e. filename without the path, and the file extension
        asset_id, extension = self._get_asset_info(input_file_path)

        # check if the file needs to be transcoded and possibly obtain a new asr_input_path
        try:
            asr_input_path = self._try_transcode(input_file_path, asset_id, extension)
        except ValueError as e:
            return APIResponse[str(e)]

        # run the ASR
        try:
            self.asr.run_asr(asr_input_path, asset_id)
        except Exception as e:
            print(e)
            return APIResponse.ASR_FAILED

        # finally process the ASR results and return the status message
        return self.asr.process_asr_output(asset_id)

    def _try_transcode(self, asr_input_path, asset_id, extension):
        if not self._is_audio_file(extension):

            if not self._is_transcodable(extension):
                raise ValueError(APIResponse.ASR_INPUT_UNACCEPTABLE.name)

            transcoding_output_path = get_transcode_output_path(
                asr_input_path, asset_id
            )

            success = transcode_to_mp3(
                asr_input_path,
                transcoding_output_path,
            )
            if success is False:
                raise ValueError(APIResponse.TRANSCODE_FAILED.name)

            return (
                transcoding_output_path  # the transcode output is the input for the ASR
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

    # clean up input files
    def _remove_files(self, path):
        for file in os.listdir(path):
            file_path = os.path.join(path, file)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print("Failed to delete {0}. Reason: {1}".format(file_path, e))
