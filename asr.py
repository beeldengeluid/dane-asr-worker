import os
import tarfile
import glob
import json
import logging
from api_util import APIResponse
import base_util

"""
This module contains functions for running audio files through Kaldi_NL to generate a speech transcript.

Moreover this module has functions for:
- validating the ASR output
- generating a JSON file (based on the 1Best.ctm transcript file)
- packaging the ASR output (as a tar)

"""
ASR_TRANSCRIPT_FILE = "1Best.ctm"
logger = logging.getLogger(__name__)


class ASR(object):
    def __init__(self, config):
        self.KALDI_NL_DIR = config["KALDI_NL_DIR"]
        self.KALDI_NL_DECODER = config["KALDI_NL_DECODER"]
        self.ASR_OUTPUT_DIR = os.path.join(
            config["BASE_FS_MOUNT_DIR"], config["ASR_OUTPUT_DIR"]
        )
        self.ASR_WORD_JSON_FILE = config["ASR_WORD_JSON_FILE"]
        self.ASR_PACKAGE_NAME = config["ASR_PACKAGE_NAME"]

    # runs the asr on the input path and puts the results in the ASR_OUTPUT_DIR dir
    def run_asr(self, input_path, asset_id):
        logger.debug("Starting ASR")
        cmd = 'cd {}; ./{} "{}" "{}/{}"'.format(
            self.KALDI_NL_DIR,
            self.KALDI_NL_DECODER,
            input_path,
            self.ASR_OUTPUT_DIR,
            asset_id,
        )
        return base_util.run_shell_command(cmd)

    def process_asr_output(self, asset_id):
        logger.debug("processing the output of {}".format(asset_id))

        if self.validate_asr_output(asset_id) is False:
            return APIResponse.ASR_OUTPUT_CORRUPT

        # create a word.json file
        self.create_word_json(asset_id, True)

        # package the output
        self.package_output(asset_id)

        # package the features and json file, so it can be used for indexing or something else
        return APIResponse.ASR_SUCCESS

    # if there is no 1Best.ctm there is something wrong with the input file or Kaldi...
    # TODO also check if the files and dir for package_output are there
    def validate_asr_output(self, asset_id):
        transcript_file = self.__get_transcript_file_path(asset_id)
        logger.debug(f"Checking if transcript exists: {transcript_file}")
        return os.path.isfile(transcript_file)

    # packages the features and the human readable output (1Best.*)
    def package_output(self, asset_id):
        output_dir = self.get_output_dir(asset_id)
        files_to_be_added = [
            "/{0}/liumlog/*.seg".format(output_dir),
            "/{0}/1Best.*".format(output_dir),
            "/{0}/intermediate/decode/*".format(output_dir),
        ]

        # also add the words json file if it was generated
        if os.path.exists(self.__get_words_file_path(asset_id)):
            files_to_be_added.append(self.__get_words_file_path(asset_id))

        tar_path = os.path.join(os.sep, output_dir, self.ASR_PACKAGE_NAME)
        tar = tarfile.open(tar_path, "w:gz")

        for pattern in files_to_be_added:
            for file_path in glob.glob(pattern):
                path, asset_id = os.path.split(file_path)
                tar.add(file_path, arcname=asset_id)

        tar.close()

    def create_word_json(self, asset_id, save_in_asr_output=False):
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

    def get_output_dir(self, asset_id):
        return os.path.join(os.sep, self.ASR_OUTPUT_DIR, asset_id)

    def __get_transcript_file_path(self, asset_id):
        return os.path.join(os.sep, self.get_output_dir(asset_id), ASR_TRANSCRIPT_FILE)

    def __get_words_file_path(self, asset_id):
        return os.path.join(
            os.sep, self.get_output_dir(asset_id), self.ASR_WORD_JSON_FILE
        )
