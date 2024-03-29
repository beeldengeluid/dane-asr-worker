from typing import Any, List
from yacs.config import CfgNode
import subprocess
import os
from pathlib import Path
import logging
import hashlib


"""
Important note on how DANE builds up it's config (which is supplied to validate_config):

    FIRST the home dir config is applied (~/.DANE/config.yml),
    THEN the local base_config.yml will overwrite anything specified
    THEN the local config.yml will overwrite anything specified there
"""
LOG_FORMAT = "%(asctime)s|%(levelname)s|%(process)d|%(module)s|%(funcName)s|%(lineno)d|%(message)s"
logger = logging.getLogger(__name__)


def validate_config(config: CfgNode, validate_file_paths: bool = True) -> bool:
    try:
        __validate_environment_variables()
    except AssertionError as e:
        print("Error malconfigured worker: env vars incomplete")
        print(str(e))
        return False

    parent_dirs_to_check: List[str] = []  # parent dirs of file paths must exist
    # check the DANE.cfg (supplied by config.yml)
    try:
        # rabbitmq settings
        assert config.RABBITMQ, "RABBITMQ"
        assert check_setting(config.RABBITMQ.HOST, str), "RABBITMQ.HOST"
        assert check_setting(config.RABBITMQ.PORT, int), "RABBITMQ.PORT"
        assert check_setting(config.RABBITMQ.EXCHANGE, str), "RABBITMQ.EXCHANGE"
        assert check_setting(
            config.RABBITMQ.RESPONSE_QUEUE, str
        ), "RABBITMQ.RESPONSE_QUEUE"
        assert check_setting(config.RABBITMQ.USER, str), "RABBITMQ.USER"
        assert check_setting(config.RABBITMQ.PASSWORD, str), "RABBITMQ.PASSWORD"

        # Elasticsearch settings
        assert config.ELASTICSEARCH, "ELASTICSEARCH"
        assert check_setting(config.ELASTICSEARCH.HOST, list), "ELASTICSEARCH.HOST"
        assert (
            len(config.ELASTICSEARCH.HOST) == 1
            and type(config.ELASTICSEARCH.HOST[0]) is str
        ), "Invalid ELASTICSEARCH.HOST"

        assert check_setting(config.ELASTICSEARCH.PORT, int), "ELASTICSEARCH.PORT"
        assert check_setting(config.ELASTICSEARCH.USER, str, True), "ELASTICSEARCH.USER"
        assert check_setting(
            config.ELASTICSEARCH.PASSWORD, str, True
        ), "ELASTICSEARCH.PASSWORD"
        assert check_setting(config.ELASTICSEARCH.SCHEME, str), "ELASTICSEARCH.SCHEME"
        assert check_setting(config.ELASTICSEARCH.INDEX, str), "ELASTICSEARCH.INDEX"

        # DANE python lib settings
        assert config.PATHS, "PATHS"
        assert check_setting(config.PATHS.TEMP_FOLDER, str), "PATHS.TEMP_FOLDER"
        assert check_setting(config.PATHS.OUT_FOLDER, str), "PATHS.OUT_FOLDER"

        # Settings for this DANE worker
        if "ASR_API" in config:
            assert check_setting(config.ASR_API.HOST, str), "ASR_API.HOST"
            assert check_setting(config.ASR_API.PORT, int), "ASR_API.PORT"
            assert check_setting(config.ASR_API.SIMULATE, bool), "ASR_API.SIMULATE"
            assert check_setting(
                config.ASR_API.WAIT_FOR_COMPLETION, bool
            ), "ASR_API.WAIT_FOR_COMPLETION"
        if "LOCAL_KALDI" in config:
            assert check_setting(
                config.LOCAL_KALDI.ASR_PACKAGE_NAME, str
            ), "LOCAL_KALDI.ASR_PACKAGE_NAME"
            assert check_setting(
                config.LOCAL_KALDI.ASR_WORD_JSON_FILE, str
            ), "LOCAL_KALDI.ASR_WORD_JSON_FILE"
            assert check_setting(
                config.LOCAL_KALDI.KALDI_NL_DIR, str
            ), "LOCAL_KALDI.KALDI_NL_DIR"
            assert check_setting(
                config.LOCAL_KALDI.KALDI_NL_DECODER, str
            ), "LOCAL_KALDI.KALDI_NL_DECODER"
            assert check_setting(
                config.LOCAL_KALDI.KALDI_NL_MODEL_DIR, str, True
            ), "LOCAL_KALDI.KALDI_NL_MODEL_DIR"
            assert check_setting(
                config.LOCAL_KALDI.KALDI_NL_MODEL_FETCHER, str
            ), "LOCAL_KALDI.KALDI_NL_MODEL_FETCHER"

        assert config.FILE_SYSTEM, "FILE_SYSTEM"
        assert check_setting(
            config.FILE_SYSTEM.BASE_MOUNT, str
        ), "FILE_SYSTEM.BASE_MOUNT"
        assert check_setting(config.FILE_SYSTEM.INPUT_DIR, str), "FILE_SYSTEM.INPUT_DIR"
        assert check_setting(
            config.FILE_SYSTEM.OUTPUT_DIR, str
        ), "FILE_SYSTEM.OUTPUT_DIR"

        assert __check_dane_dependencies(config.DANE_DEPENDENCIES), "DANE_DEPENDENCIES"

        # validate file paths (not while unit testing)
        if validate_file_paths:
            __validate_parent_dirs(parent_dirs_to_check)
            __validate_dane_paths(config.PATHS.TEMP_FOLDER, config.PATHS.OUT_FOLDER)

    except AssertionError as e:
        print(f"Configuration error: {str(e)}")
        return False

    return True


def __validate_environment_variables() -> None:
    # self.UNIT_TESTING = os.getenv('DW_ASR_UNIT_TESTING', False)
    try:
        assert True  # TODO add secrets from the config.yml to the env
    except AssertionError as e:
        raise (e)


def __validate_dane_paths(dane_temp_folder: str, dane_out_folder: str) -> None:
    i_dir = Path(dane_temp_folder)
    o_dir = Path(dane_out_folder)

    try:
        assert os.path.exists(
            i_dir.parent.absolute()
        ), f"{i_dir.parent.absolute()} does not exist"
        assert os.path.exists(
            o_dir.parent.absolute()
        ), f"{o_dir.parent.absolute()} does not exist"
    except AssertionError as e:
        raise (e)


def check_setting(setting: Any, t: type, optional=False) -> bool:
    return (type(setting) is t and optional is False) or (
        optional and (setting is None or type(setting) is t)
    )


def __check_dane_dependencies(deps: Any) -> bool:
    deps_to_check: list = deps if type(deps) is list else []
    deps_allowed = ["DOWNLOAD", "BG_DOWNLOAD"]
    return any(dep in deps_allowed for dep in deps_to_check)


def __validate_parent_dirs(paths: list) -> None:
    try:
        for p in paths:
            assert os.path.exists(
                Path(p).parent.absolute()
            ), f"Parent dir of file does not exist: {p}"
    except AssertionError as e:
        raise (e)


# used by asr.py and transcode.py
def run_shell_command(cmd: str) -> bool:
    logger.info(cmd)
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,  # needed to support file glob
        )

        stdout, stderr = process.communicate()
        logger.info(stdout)
        logger.error(stderr)
        """
        while True:
            if not process.stdout or not process.stderr:
                logger.warning("no stdout or stderr in process")
                break

            is_error = False

            # first try to read the stdout
            line = process.stdout.readline()
            if not line:  # some processes use stderr instead
                line = process.stderr.readline()
                is_error = True

            if line:
                if is_error:
                    logger.error(line)
                else:
                    logger.info(line)
            else:
                logger.info("nothing left in stdout or stderr")
                break
        """

        logger.info(f"Process is done: return code {process.returncode}")
        return process.returncode == 0
    except subprocess.CalledProcessError:
        logger.exception("CalledProcessError")
        return False
    except Exception:
        logger.exception("Exception")
        return False


def hash_string(s: str) -> str:
    return hashlib.sha224("{0}".format(s).encode("utf-8")).hexdigest()
