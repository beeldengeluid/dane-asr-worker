import logging
import os

from base_util import get_asset_info, asr_output_dir
from config import s3_endpoint_url, s3_bucket, s3_folder_in_bucket
from download import download_uri
from kaldi_nl import run_asr  # import whisper
from s3_util import S3Store
from transcode import try_transcode
from transcript import TXT_FILE, CTM_FILE, JSON_FILE, generate_transcript

logger = logging.getLogger(__name__)


def run(input_uri: str, output_uri: str) -> bool:
    logger.info(f"Processing {input_uri} (save to --> {output_uri})")
    # 1. download input
    result = download_uri(input_uri)
    logger.info(result)
    if not result:
        logger.error("Could not obtain input, quitting...")
        return False

    input_path = result.file_path
    asset_id, extension = get_asset_info(input_path)
    output_path = asr_output_dir(input_path)

    # 2. Check if the input file is suitable for processing any further
    transcoded_file_path = try_transcode(input_path, asset_id, extension)
    if not transcoded_file_path:
        logger.error("The transcode failed to yield a valid file to continue with")
        return False
    else:
        input_path = transcoded_file_path

    # 3. run ASR
    if not asr_already_done(output_path):
        logger.info("No Kaldi_NL output found")
        run_asr(input_path, output_path)
    else:
        logger.info(f"Kaldi_NL output already present in {output_path}")

    # 4. generate JSON transcript
    if not transcript_already_done(output_path):
        logger.info("No transcript.json found")
        success = generate_transcript(output_path)
        if not success:
            logger.warning("Could not generate transcript.json")
    else:
        logger.info(f"transcript.json already present in {output_path}")

    # 5. transfer output
    if output_uri:
        transfer_asr_output(output_path, asset_id)
    else:
        logger.info("No output_uri specified, so all is done")
    return True


# if (S3) output_uri is supplied transfers data to S3 location
def transfer_asr_output(output_path: str, asset_id: str) -> bool:
    logger.info(f"Transferring {output_path} to S3 (asset={asset_id})")
    if any(
        [
            not x
            for x in [
                s3_endpoint_url,
                s3_bucket,
                s3_folder_in_bucket,
            ]
        ]
    ):
        logger.warning(
            "TRANSFER_ON_COMPLETION configured without all the necessary S3 settings"
        )
        return False

    s3 = S3Store(s3_endpoint_url)
    return s3.transfer_to_s3(
        s3_bucket,
        os.path.join(
            s3_folder_in_bucket, asset_id
        ),  # assets/<program ID>__<carrier ID>
        [
            os.path.join(output_path, CTM_FILE),
            os.path.join(output_path, TXT_FILE),
        ],
    )


# check if there is both a 1Best.txt and 1Best.ctm
def asr_already_done(output_dir):
    return all(
        [
            os.path.exists(os.path.join(output_dir, output_file))
            for output_file in [TXT_FILE, CTM_FILE]
        ]
    )


# check if there is a transcript.json
def transcript_already_done(output_dir):
    return os.path.exists(os.path.join(output_dir, JSON_FILE))
