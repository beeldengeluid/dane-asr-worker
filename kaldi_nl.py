import logging
from base_util import run_shell_command

logger = logging.getLogger(__name__)


def run_asr(input_path, output_dir) -> bool:
    logger.info(f"Starting ASR on {input_path}")
    cmd = 'cd {}; ./{} "{}" "{}"'.format(
        "/opt/Kaldi_NL",
        "decode_OH.sh",
        input_path,
        output_dir,
    )
    try:
        run_shell_command(cmd)
    except Exception:
        logger.exception("Kaldi command failed")
        return False
    return True
