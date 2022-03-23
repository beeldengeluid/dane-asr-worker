from dataclasses import dataclass
from typing import List
import os.path

import tests.data
from worker import ParsedResult

TEST_DATA_PATH = tests.data.__path__[0]


@dataclass
class AsrOutputCase:
    id: str
    output_dir: str
    expected_results: List[ParsedResult]


asr_output_cases = [
    AsrOutputCase(
        id="BG27239MPG_-HRE000033CB",
        output_dir=os.path.join(
            TEST_DATA_PATH, "asr_output", "BG27239MPG_-HRE000033CB"
        ),
        expected_results=[
            {
                "words": "Weet jij waar door robert.",
                "wordTimes": [1360, 1440, 1570, 2990, 3220],
                "start": 0.0,
                "sequenceNr": 0,
                "fragmentId": "1302226",
                "carrierId": "1303068",
            },
            {
                "words": "Ja je.",
                "wordTimes": [29650, 30470],
                "start": 28000.0,
                "sequenceNr": 1,
                "fragmentId": "1302226",
                "carrierId": "1303068",
            },
            {
                "words": "Ronnie.",
                "wordTimes": [35170],
                "start": 34000.0,
                "sequenceNr": 2,
                "fragmentId": "1302226",
                "carrierId": "1303068",
            },
            {
                "words": "Kinderen nou.",
                "wordTimes": [66640, 68020],
                "start": 60000.0,
                "sequenceNr": 3,
                "fragmentId": "1302226",
                "carrierId": "1303068",
            },
            {
                "words": "Zei ja soekarno in dacht kali yang indonesia.",
                "wordTimes": [80070, 80300, 80560, 83970, 84150, 84450, 85140, 87210],
                "start": 74000.0,
                "sequenceNr": 4,
                "fragmentId": "1302226",
                "carrierId": "1303068",
            },
            {
                "words": "Indonesia.",
                "wordTimes": [93610],
                "start": 89000.0,
                "sequenceNr": 5,
                "fragmentId": "1302226",
                "carrierId": "1303068",
            },
            {
                "words": "Waarom indonesia olympia nippon indonesia.",
                "wordTimes": [94810, 98830, 103060, 103540, 104340],
                "start": 94000.0,
                "sequenceNr": 6,
                "fragmentId": "1302226",
                "carrierId": "1303068",
            },
            {
                "words": "Jan programma staan maar marie maar ja ik doe.",
                "wordTimes": [
                    108370,
                    111020,
                    111410,
                    111530,
                    112220,
                    117040,
                    117650,
                    117900,
                    118020,
                ],
                "start": 105000.0,
                "sequenceNr": 7,
                "fragmentId": "1302226",
                "carrierId": "1303068",
            },
            {
                "words": "Ha ha.",
                "wordTimes": [179800, 182710],
                "start": 179000.0,
                "sequenceNr": 8,
                "fragmentId": "1302226",
                "carrierId": "1303068",
            },
            {
                "words": "Up.",
                "wordTimes": [297950],
                "start": 292000.0,
                "sequenceNr": 9,
                "fragmentId": "1302226",
                "carrierId": "1303068",
            },
            {
                "words": "Mmm.",
                "wordTimes": [303710],
                "start": 299000.0,
                "sequenceNr": 10,
                "fragmentId": "1302226",
                "carrierId": "1303068",
            },
        ],
    )
]
