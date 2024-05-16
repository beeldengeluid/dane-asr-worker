import logging
import ntpath
import os
from pathlib import Path
import requests
from time import time
from typing import Optional
from urllib.parse import urlparse

from dane import Document
from models import DownloadResult

logger = logging.getLogger(__name__)


# the file name without extension is used as an asset ID by the ASR container to save the results
def get_asset_id(input_file: str) -> str:
    # grab the file_name from the path
    file_name = ntpath.basename(input_file)

    # split up the file in asset_id (used for creating a subfolder in the output) and extension
    asset_id, extension = os.path.splitext(file_name)
    logger.info("working with this asset ID {}".format(asset_id))
    return asset_id


def get_asr_output_dir(asr_output_dir: str, asset_id: str) -> str:
    return os.path.join(asr_output_dir, asset_id)


def validate_data_dirs(asr_input_dir: str, asr_output_dir: str) -> bool:
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


# TODO input_file_path = doc.target.get("url")
def fetch_input_file(doc: Document, asr_input_dir: str, dane_es_handler=None):
    download_result = fetch_downloaded_content(dane_es_handler, doc)

    # step 2: try to download the file if no DANE download worker was configured
    if download_result is None:
        logger.info(
            "The file was not downloaded by the DANE worker, downloading it myself..."
        )
        download_result = download_content(doc, asr_input_dir)
    return download_result


def fetch_downloaded_content(
    dane_es_handler, doc: Document
) -> Optional[DownloadResult]:
    logger.info("checking download worker output")
    possibles = dane_es_handler.searchResult(doc._id, "DOWNLOAD")
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


# https://www.openbeelden.nl/files/29/29494.29451.WEEKNUMMER243-HRE00015742.mp4
def download_content(doc: Document, asr_input_dir: str) -> Optional[DownloadResult]:
    if not doc.target or "url" not in doc.target or not doc.target["url"]:
        logger.info("No url found in DANE doc")
        return None

    logger.info("downloading {}".format(doc.target["url"]))
    fn = os.path.basename(urlparse(doc.target["url"]).path)
    # fn = unquote(fn)
    # fn = doc.target['url'][doc.target['url'].rfind('/') +1:]
    output_file = os.path.join(asr_input_dir, fn)
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


def cleanup_input_file(
    asr_input_dir: str, input_file: str, actually_delete: bool
) -> bool:
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
        os.chdir(asr_input_dir)  # cd /mnt/dane-fs/input-files
        os.removedirs(
            f".{input_file[len(asr_input_dir):input_file.rfind(os.sep)]}"
        )  # /03/d2/8a/03d28a03643a981284b403b91b95f6048576c234
        logger.info("Deleted empty input dirs too")
    except OSError:
        logger.exception("OSError while removing empty input file dirs")
    except FileNotFoundError:
        logger.exception("FileNotFoundError while removing empty input file dirs")

    return True  # return True even if empty dirs were not removed
