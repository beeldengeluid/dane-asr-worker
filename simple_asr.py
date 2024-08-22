import logging
from download import download_uri
from base_util import run_shell_command

logger = logging.getLogger(__name__)

def run(input_uri: str, output_uri: str) -> bool:
    logger.info("calling Kaldi_NL directly")
    result = download_uri(input_uri)
    logger.info(result)
    _run_asr(result.file_path, "kaldi-nl-test")
    return True

# temporarily in this module
def _run_asr(input_path, asset_id) -> bool:
    logger.info(f"Starting ASR on {input_path}")
    cmd = 'cd {}; ./{} "{}" "{}/{}"'.format(
        "/opt/Kaldi_NL",
        "decode_OH.sh",
        input_path,
        "./data",
        asset_id,
    )
    try:
        run_shell_command(cmd)
    except Exception:
        logger.exception("Kaldi command failed")
        return False

    # finally process the ASR results and return the status message
    # return self._process_asr_output(asset_id)
    return True
