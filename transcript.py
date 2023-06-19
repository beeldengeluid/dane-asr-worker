import os
import codecs
import logging
from codecs import StreamReaderWriter
from typing import TypedDict, List


logger = logging.getLogger(__name__)


class ParsedResult(TypedDict):
    words: str
    wordTimes: List[int]
    start: float
    sequenceNr: int
    fragmentId: str
    carrierId: str


# asr_output_dir e.g mount/asr-output/1272-128104-0000
# NOTE: only handles Kaldi_NL generated files at this moment
def generate_transcript(asr_output_dir: str) -> List[ParsedResult] | None:
    logger.info(f"Generating transcript from: {asr_output_dir}")
    if not _is_valid_kaldi_output(asr_output_dir):
        return None

    transcript = None
    try:
        with codecs.open(
            os.path.join(asr_output_dir, "1Best.ctm"), encoding="utf-8"
        ) as times_file:
            times = _extract_time_info(times_file)

        with codecs.open(
            os.path.join(asr_output_dir, "1Best.txt"), encoding="utf-8"
        ) as asr_file:
            transcript = _parse_asr_results(asr_file, times)
    except EnvironmentError as e:  # OSError or IOError...
        logger.exception(os.strerror(e.errno))

    return transcript


def delete_asr_output(path: str) -> bool:
    # Clean up the extracted dir
    # shutil.rmtree(path)
    logger.info("Cleaned up folder {}".format(path))
    return False


def _is_valid_kaldi_output(path: str) -> bool:
    if not all(
        [
            os.path.exists(p)
            for p in [
                path,
                os.path.join(path, "1Best.ctm"),
                os.path.join(path, "1Best.txt"),
            ]
        ]
    ):
        logger.error("Error: ASR output dir does not exist")
        return False

    return True


def _parse_asr_results(
    asr_file: StreamReaderWriter, times: List[int]
) -> List[ParsedResult]:
    transcript = []
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
            logger.info(
                "Number of words does not match word-times for file: {}, "
                "current position in file: {}".format(asr_file.name, cur_pos)
            )

        # extract the carrier and fragment ID
        carrier_fragid = parts[1].split(" ")[0].split(".")
        carrier = carrier_fragid[0]
        fragid = carrier_fragid[1]

        # extract the starttime
        sTime = parts[1].split(" ")[1].replace(")", "").split(".")
        starttime = int(sTime[0]) * 1000

        subtitle: ParsedResult = {
            "words": words,
            "wordTimes": word_times,
            "start": float(starttime),
            "sequenceNr": i,
            "fragmentId": fragid,
            "carrierId": carrier,
        }
        transcript.append(subtitle)
        i += 1
    return transcript


def _extract_time_info(times_file: StreamReaderWriter) -> List[int]:
    times = []

    for line in times_file:
        time_string = line.split(" ")[2]
        ms_value = int(float(time_string) * 1000)
        times.append(ms_value)

    return times
