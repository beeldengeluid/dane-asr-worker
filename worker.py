import DANE.base_classes
from DANE.config import cfg
from DANE import Result

import os
import codecs
import ntpath
from pathlib import Path
import json
import requests
from urllib.parse import urlparse
from time import sleep
import hashlib
from base_util import init_logger, validate_config

# from work_processor import process_input_file

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


class asr_worker(DANE.base_classes.base_worker):
    def __init__(self, config):
        self.logger = init_logger(config)
        self.logger.debug(config)

        self.UNIT_TESTING = os.getenv("DW_ASR_UNIT_TESTING", False)

        if not validate_config(config, not self.UNIT_TESTING):
            self.logger.error("Invalid config, quitting")
            quit()

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

            # ASR API settings
            self.ASR_API_HOST: str = config.ASR_API.HOST
            self.ASR_API_PORT: int = config.ASR_API.PORT
            self.ASR_API_WAIT_FOR_COMPLETION: bool = config.ASR_API.WAIT_FOR_COMPLETION
            self.ASR_API_SIMULATE: bool = config.ASR_API.SIMULATE
            self.DANE_DEPENDENCIES: list = (
                config.DANE_DEPENDENCIES if "DANE_DEPENDENCIES" in config else []
            )
            self.DELETE_INPUT_ON_COMPLETION: bool = (
                config.DELETE_INPUT_ON_COMPLETION
                if "DELETE_INPUT_ON_COMPLETION" in config
                else []
            )
        except AttributeError:
            self.logger.exception("Missing configuration setting")
            quit()

        # check if the file system is setup properly
        if not self.validate_data_dirs(self.ASR_INPUT_DIR, self.ASR_OUTPUT_DIR):
            self.logger.debug("ERROR: data dirs not configured properly")
            quit()

        # we specify a queue name because every worker of this type should
        # listen to the same queue
        self.__queue_name = (
            "ASR"  # this is the queue that receives the work and NOT the reply queue
        )
        self.__binding_key = "#.ASR"  # ['Video.ASR', 'Sound.ASR']#'#.ASR'
        self.__depends_on = self.DANE_DEPENDENCIES

        needs_asr_service = not self.UNIT_TESTING
        if needs_asr_service and not self.wait_for_asr_service():
            self.logger.error(
                "Error: after 100 attempts the ASR service is still not ready! Stopping worker"
            )
            quit()

        super().__init__(
            self.__queue_name,
            self.__binding_key,
            config,
            self.__depends_on,
            auto_connect=not self.UNIT_TESTING,
            no_api=self.UNIT_TESTING,
        )

    def __get_downloader_type(self):
        self.logger.debug("determining downloader type")
        if "DOWNLOAD" in self.DANE_DEPENDENCIES:
            return "DOWNLOAD"
        elif "BG_DOWNLOAD" in self.DANE_DEPENDENCIES:
            return "BG_DOWNLOAD"
        self.logger.warning(
            "Warning: did not find DOWNLOAD or BG_DOWNLOAD in worker dependencies"
        )
        return None

    # make sure the service is ready before letting the server know that this worker is ready
    def wait_for_asr_service(self, attempts=0):
        url = "http://{}:{}/ping".format(self.ASR_API_HOST, self.ASR_API_PORT)
        resp = requests.get(url)
        self.logger.info(resp.status_code)
        self.logger.info(resp.text)
        if resp.status_code == 200 and resp.text == "pong":
            return True
        if attempts < 100:  # TODO add to configuration
            sleep(2)
            self.wait_for_asr_service(attempts + 1)
        return False

    """----------------------------------INIT VALIDATION FUNCTIONS ---------------------------------"""

    def validate_data_dirs(self, asr_input_dir: str, asr_output_dir: str):
        i_dir = Path(asr_input_dir)
        o_dir = Path(asr_output_dir)

        if not os.path.exists(i_dir.parent.absolute()):
            self.logger.debug(
                "{} does not exist. Make sure BASE_MOUNT_DIR exists before retrying".format(
                    i_dir.parent.absolute()
                )
            )
            return False

        # make sure the input and output dirs are there
        try:
            os.makedirs(i_dir, 0o755)
            self.logger.debug("created ASR input dir: {}".format(i_dir))
        except FileExistsError as e:
            self.logger.debug(e)

        try:
            os.makedirs(o_dir, 0o755)
            self.logger.debug("created ASR output dir: {}".format(o_dir))
        except FileExistsError as e:
            self.logger.debug(e)

        return True

    """----------------------------------INTERACTION WITH DANE SERVER ---------------------------------"""

    # DANE callback function, called whenever there is a job for this worker
    def callback(self, task, doc):
        self.logger.debug("receiving a task from the DANE (mock) server!")
        self.logger.debug(task)
        self.logger.debug(doc)

        # TODO check if a transcript was already generated

        # either DOWNLOAD, BG_DOWNLOAD or None (meaning the ASR worker will try to download the data itself)
        downloader_type = self.__get_downloader_type()

        # step 1 (temporary, until DOWNLOAD depency accepts params to override download dir)
        input_file = (
            self.fetch_downloaded_content(doc) if downloader_type is not None else None
        )

        if input_file is None:
            self.logger.debug(
                "The file was not downloaded by the DANE worker, downloading it myself..."
            )
            input_file = self.download_content(doc)
            if input_file is None:
                return {
                    "state": 500,
                    "message": "Could not download the document content",
                }

        # step 2 create hash of input file to use for progress tracking
        input_hash = self.hash_string(input_file)

        # step 3 submit the input file to the ASR service
        asr_result = self.submit_asr_job(input_file, input_hash)
        self.logger.debug(asr_result)

        # step 4 generate a transcript from the ASR service's output
        if asr_result["state"] == 200:
            # TODO change this, harmonize the asset ID with the process ID (pid)
            asr_output_dir = self.get_asr_output_dir(self.get_asset_id(input_file))
            transcript = self.asr_output_to_transcript(asr_output_dir)
            if transcript:
                if self.cleanup_input_file(input_file, self.DELETE_INPUT_ON_COMPLETION):
                    self.save_to_dane_index(task, transcript, asr_output_dir)
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
        return asr_result

    def cleanup_input_file(self, input_file, actually_delete):
        self.logger.debug(f"Verifying deletion of input file: {input_file}")
        if actually_delete is False:
            return True

        # first remove the input file
        try:
            os.remove(input_file)
            self.logger.info(f"Deleted ASR input file: {input_file}")
            # also remove the transcoded mp3 file (if any)
            if input_file.find(".mp3") == -1 and input_file.find(".") != -1:
                mp3_input_file = f"{input_file[:input_file.rfind('.')]}.mp3"
                if os.path.exists(mp3_input_file):
                    os.remove(mp3_input_file)
                    self.logger.info(f"Deleted mp3 transcode file: {mp3_input_file}")
        except OSError:
            self.logger.exception("Could not delete input file")
            return False

        # now remove the "chunked path" from /mnt/dane-fs/input-files/03/d2/8a/03d28a03643a981284b403b91b95f6048576c234/xyz.mp4
        try:
            os.chdir(self.ASR_INPUT_DIR)  # cd /mnt/dane-fs/input-files
            os.removedirs(
                f".{input_file[len(self.ASR_INPUT_DIR):input_file.rfind(os.sep)]}"
            )  # /03/d2/8a/03d28a03643a981284b403b91b95f6048576c234
            self.logger.info("Deleted empty input dirs too")
        except OSError:
            self.logger.exception("OSError while removing empty input file dirs")
        except FileNotFoundError:
            self.logger.exception(
                "FileNotFoundError while removing empty input file dirs"
            )

        return True  # return True even if empty dirs were not removed

    # Note: the supplied transcript is EXACTLY the same as what we use in layer__asr in the collection indices,
    # meaning it should be quite trivial to append the DANE output into a collection
    def save_to_dane_index(self, task, transcript, asr_output_dir):
        self.logger.debug("saving results to DANE, task id={0}".format(task._id))
        # TODO figure out the multiple lines per transcript (refresh my memory)
        r = Result(
            self.generator,
            payload={"transcript": transcript, "asr_output_dir": asr_output_dir},
            api=self.handler,
        )
        r.save(task._id)

    """----------------------------------ID MANAGEMENT FUNCTIONS ---------------------------------"""

    # the file name without extension is used as an asset ID by the ASR container to save the results
    def get_asset_id(self, input_file):
        # grab the file_name from the path
        file_name = ntpath.basename(input_file)

        # split up the file in asset_id (used for creating a subfolder in the output) and extension
        asset_id, extension = os.path.splitext(file_name)
        self.logger.debug("working with this asset ID {}".format(asset_id))
        return asset_id

    def get_asr_output_dir(self, asset_id):
        return os.path.join(self.ASR_OUTPUT_DIR, asset_id)

    def hash_string(self, s):
        return hashlib.sha224("{0}".format(s).encode("utf-8")).hexdigest()

    """----------------------------------DOWNLOAD FUNCTIONS ---------------------------------"""

    # https://www.openbeelden.nl/files/29/29494.29451.WEEKNUMMER243-HRE00015742.mp4
    def download_content(self, doc):
        if not doc.target or "url" not in doc.target or not doc.target["url"]:
            self.logger.debug("No url found in DANE doc")
            return None

        self.logger.debug("downloading {}".format(doc.target["url"]))
        fn = os.path.basename(urlparse(doc.target["url"]).path)
        # fn = unquote(fn)
        # fn = doc.target['url'][doc.target['url'].rfind('/') +1:]
        output_file = os.path.join(self.ASR_INPUT_DIR, fn)
        self.logger.debug("saving to file {}".format(fn))

        # download if the file is not present (preventing unnecessary downloads)
        if not os.path.exists(output_file):
            with open(output_file, "wb") as file:
                response = requests.get(doc.target["url"])
                file.write(response.content)
                file.close()
        return fn

    def fetch_downloaded_content(self, doc):
        self.logger.debug("checking download worker output")
        downloader_type = self.__get_downloader_type()
        if not downloader_type:
            return None

        try:
            possibles = self.handler.searchResult(doc._id, downloader_type)
            self.logger.debug(possibles)
            return possibles[0].payload[
                "file_path"
            ]  # both used in BG_DOWNLOAD and DOWNLOAD DANE.Result
        except KeyError as e:
            self.logger.exception(e)

        return None

    """----------------------------------INTERACT WITH ASR SERVIVCE (DOCKER CONTAINER) --------------------------"""

    def submit_asr_job(self, input_file, input_hash):
        self.logger.debug(
            "Going to submit {} to the ASR service, using PID={}".format(
                input_file, input_hash
            )
        )
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
            self.logger.debug(dane_asr_api_url)
            resp = requests.put(dane_asr_api_url)
        except requests.exceptions.ConnectionError as e:
            self.logger.error(e)
            return {
                "state": 500,
                "message": "Failure: could not connect to the ASR service",
            }

        # return the result right away if in synchronous mode
        if self.ASR_API_WAIT_FOR_COMPLETION:
            if resp.status_code == 200:
                self.logger.debug("The ASR service is done, returning the results")
                data = json.loads(resp.text)
                return data
            else:
                self.logger.debug("error returned")
                self.logger.debug(resp.text)
                return {
                    "state": 500,
                    "message": "Failure: the ASR service returned an error",
                }

        # else start polling the ASR service, using the input_hash for reference (TODO synch with asset_id)
        self.logger.debug("Polling the ASR service to check when it is finished")
        while True:
            resp = requests.get(
                "http://{0}:{1}/api/{2}/{3}".format(
                    self.ASR_API_HOST,
                    self.ASR_API_PORT,
                    "process",  # replace later with process
                    input_hash,
                )
            )
            process_msg = json.loads(resp.text)

            state = process_msg["state"] if "state" in process_msg else 500
            finished = process_msg["finished"] if "finished" in process_msg else False

            if finished:
                return {
                    "state": 200,
                    "message": "The ASR service generated valid output {}".format(
                        input_file
                    ),
                }
            elif state == 500:
                return {
                    "state": 500,
                    "message": "The ASR failed to produce the required output {}".format(
                        input_file
                    ),
                }
            elif state == 404:
                return {
                    "state": 404,
                    "message": "The ASR failed to find the required input {}".format(
                        input_file
                    ),
                }

            # wait for one second before polling again
            sleep(1)

        return {
            "state": 500,
            "message": "The ASR failed to produce the required output {}".format(
                input_file
            ),
        }

    """----------------------------------PROCESS ASR OUTPUT (DOCKER MOUNT) --------------------------"""

    # mount/asr-output/1272-128104-0000
    def asr_output_to_transcript(self, asr_output_dir):
        self.logger.debug(
            "generating a transcript from the ASR output in: {0}".format(asr_output_dir)
        )
        transcriptions = None
        if os.path.exists(asr_output_dir):
            try:
                with codecs.open(
                    os.path.join(asr_output_dir, "1Best.ctm"), encoding="utf-8"
                ) as times_file:
                    times = self.__extractTimeInfo(times_file)

                with codecs.open(
                    os.path.join(asr_output_dir, "1Best.txt"), encoding="utf-8"
                ) as asr_file:
                    transcriptions = self.__parseASRResults(asr_file, times)
            except EnvironmentError as e:  # OSError or IOError...
                self.logger.debug(os.strerror(e.errno))

            # Clean up the extracted dir
            # shutil.rmtree(asr_output_dir)
            # self.logger.debug("Cleaned up folder {}".format(asr_output_dir))
        else:
            self.logger.debug(
                "Error: cannot generate transcript; ASR output dir does not exist"
            )

        return transcriptions

    def __parseASRResults(self, asr_file, times):
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
                self.logger.debug(
                    "Number of words does not match word-times for file: {}, "
                    "current position in file: {}".format(asr_file.name, cur_pos)
                )

            # extract the carrier and fragment ID
            carrier_fragid = parts[1].split(" ")[0].split(".")
            carrier = carrier_fragid[0]
            fragid = carrier_fragid[1]

            # extract the starttime
            sTime = parts[1].split(" ")[1].replace(")", "")
            sTime = sTime.split(".")
            starttime = int(sTime[0]) * 1000

            subtitle = {
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

    def __extractTimeInfo(self, times_file):
        times = []

        for line in times_file:
            time_string = line.split(" ")[2]
            ms_value = int(float(time_string) * 1000)
            times.append(ms_value)

        return times


# Start the worker
if __name__ == "__main__":
    w = asr_worker(cfg)
    try:
        w.run()
    except (KeyboardInterrupt, SystemExit):
        w.stop()
