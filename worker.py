import logging
import sys

from base_util import LOG_FORMAT
import complicated_asr
import simple_asr


# initialises the root logger
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,  # configure a stream handler only for now (single handler)
    format=LOG_FORMAT,
)
logger = logging.getLogger()


# Start the worker
if __name__ == "__main__":
    from argparse import ArgumentParser
    from base_util import LOG_FORMAT

    # first read the CLI arguments
    parser = ArgumentParser(description="dane-video-segmentation-worker")
    parser.add_argument("--input", action="store", dest="input_uri", default=None)
    parser.add_argument("--output", action="store", dest="output_uri", default=None)
    parser.add_argument("--dane", action="store", dest="dane", default="n")
    parser.add_argument("--log", action="store", dest="loglevel", default="INFO")
    args = parser.parse_args()

    # initialises the root logger
    logging.basicConfig(
        stream=sys.stdout,  # configure a stream handler only for now (single handler)
        format=LOG_FORMAT,
    )

    # setting the loglevel
    log_level = args.loglevel.upper()
    logger.setLevel(log_level)
    logger.info(f"Logger initialized (log level: {log_level})")
    logger.info(f"Got the following CMD line arguments: {args}")

    if args.dane == "n":
        logger.info("very good, running Kaldi_NL")
        simple_asr.run(args.input_uri, args.output_uri)
    else:
        complicated_asr.run()
