import logging
import os
import requests
import time
from typing import Optional
from urllib.parse import urlparse
from dane.s3_util import S3Store, parse_s3_uri, validate_s3_uri
from models import DownloadResult

logger = logging.getLogger(__name__)

S3_ENDPOINT_URL = "https://s3.eu-west-1.amazonaws.com/"  # TODO read from conf


def get_download_dir():
    return "./data"  # TODO configure


def download_uri(uri: str) -> Optional[DownloadResult]:
    logger.info(f"Trying to download {uri}")
    if validate_s3_uri(uri):
        logger.info("URI seems to be an s3 uri")
        return s3_download(uri)
    return http_download(uri)


# TODO test this!
def http_download(url: str) -> Optional[DownloadResult]:
    logger.info(f"Downloading {url}")
    fn = os.path.basename(urlparse(url).path)
    # fn = unquote(fn)
    # fn = doc.target['url'][doc.target['url'].rfind('/') +1:]
    output_file = os.path.join(get_download_dir(), fn)
    logger.info(f"Saving to file {fn}")

    # download if the file is not present (preventing unnecessary downloads)
    start_time = time.time()
    if not os.path.exists(output_file):
        with open(output_file, "wb") as file:
            response = requests.get(url)
            file.write(response.content)
            file.close()
    download_time = (time.time() - start_time) * 1000  # time in ms
    return DownloadResult(
        output_file,  # NOTE or output_file? hmmm
        download_time,  # TODO add mime_type and content_length
    )


# e.g. s3://dane-asset-staging-gb/assets/2101608170158176431__NOS_JOURNAAL_-WON01513227.mp4
def s3_download(s3_uri: str) -> Optional[DownloadResult]:
    logger.info(f"Downloading {s3_uri}")
    if not validate_s3_uri(s3_uri):
        logger.error(f"Invalid S3 URI: {s3_uri}")
        return None

    # source_id = get_source_id(s3_uri)
    start_time = time.time()
    output_folder = get_download_dir()

    # TODO download the content into get_download_dir()
    s3 = S3Store(S3_ENDPOINT_URL)
    bucket, object_name = parse_s3_uri(s3_uri)
    logger.info(f"OBJECT NAME: {object_name}")
    input_file_path = os.path.join(
        get_download_dir(),
        # source_id,
        os.path.basename(object_name),  # i.e. visxp_prep__<source_id>.tar.gz
    )
    success = s3.download_file(bucket, object_name, output_folder)
    if success:
        download_time = time.time() - start_time
        return DownloadResult(
            input_file_path,
            download_time,
        )
    logger.error("Failed to download input data from S3")
    return None
