import pytest
from transcript import generate_transcript
from tests.unit.output_cases import asr_output_cases


@pytest.mark.parametrize(
    "output_dir, expected_results",
    [
        (
            case.output_dir,
            case.expected_results,
        )
        for case in asr_output_cases
    ],
)
def test_generate_transcript(output_dir, expected_results):
    assert generate_transcript(output_dir) == expected_results
