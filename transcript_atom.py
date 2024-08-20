import argparse
import os
import codecs
import logging
import json
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
def generate_transcript(asr_output_dir: str, ctm_file_name: str, txt_file_name: str) -> List[ParsedResult] | None:
    logger.info(f"Generating transcript from: {asr_output_dir}")
    if not _is_valid_kaldi_output(asr_output_dir, ctm_file_name, txt_file_name):
        return None
    transcript = None
    try:
        with codecs.open(
            os.path.join(asr_output_dir, ctm_file_name), encoding="utf-8"
        ) as times_file:
            times = _extract_time_info(times_file)

        with codecs.open(
            os.path.join(asr_output_dir, txt_file_name), encoding="utf-8"
        ) as asr_file:
            transcript = _parse_asr_results(asr_file, times)
    except EnvironmentError as e:  # OSError or IOError...
        logger.exception(os.strerror(e.errno))

    return transcript


def save_transcript(transcript: List[ParsedResult], json_output_dir: str, output_file_name: str) -> bool:
    try:
        path = os.path.join(json_output_dir, output_file_name)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(transcript, f, ensure_ascii=False, indent=4)
    except Exception:
        logger.exception("Failed to save transcript as josn")
        return False
    return True


def _is_valid_kaldi_output(path: str, ctm_file_name: str, txt_file_name: str) -> bool:
    if not all(
        [
            os.path.exists(p)
            for p in [
                path,
                os.path.join(path, ctm_file_name),
                os.path.join(path, txt_file_name),
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


if __name__ == "__main__":
    # SET PARSER
    parser = argparse.ArgumentParser(description='define input and output file location')
    parser.add_argument('-asr_input_dir',
                        metavar=('asr_input_dir'),
                        help='place where the (ctm and txt) asr output are stored')
    parser.add_argument('-output_dir',
                        metavar=('output_dir'),
                        help='place where the json file is stored')
    parser.add_argument('-ctm_file',
                        metavar=('ctm_file'),
                        default="1Best.ctm",  # contains the word timings
                        help='name of the ctm file including extention')
    parser.add_argument('-txt_file',
                        metavar=('ctm_file'),
                        default="1Best.txt",  # contains the word timings
                        help='name of the txt file including extention')
    parser.add_argument('-output_file',
                        metavar=('output_file'),
                        default="1Best.json",  # contains the word timings
                        help='name of the txt file including extention')
    args = parser.parse_args()
    transcript = generate_transcript(args.asr_input_dir, args.ctm_file, args.txt_file)
    save = save_transcript(transcript, args.output_dir, args.output_file)
