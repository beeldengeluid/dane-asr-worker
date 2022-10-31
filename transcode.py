import logging
import os
import base_util
from typing import Optional


"""
This class supplies the function for transcoding valid video files into mp3 format (i.e. valid input for Kaldi)
"""


logger = logging.getLogger(__name__)


def transcode_to_mp3(self, path: str, asr_path: str) -> bool:
    logger.debug(f"Encoding file: {path}")
    cmd = "ffmpeg -i {0} {1}".format(path, asr_path)
    return base_util.run_shell_command(cmd)


def get_transcode_output_path(
    self, input_path: os.PathLike, asset_id: os.PathLike
) -> Optional[str]:
    try:
        return os.path.join(  # normalise all path elements to strings to avoid "Can't mix strings and bytes in path components"
            os.sep,
            f"{os.path.dirname(input_path)}",  # the dir the input file is in
            f"{asset_id}.mp3",  # same name as input file, but with mp3 extension
        )
    except TypeError:
        logger.exception("Error assembling transcode output path")
        return None