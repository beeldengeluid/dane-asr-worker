import pytest
from yacs.config import CfgNode

from base_util import __check_dane_dependencies, validate_config, hash_string


def test_validate_config(config: CfgNode, environment_variables):
    assert validate_config(config, False)


@pytest.mark.parametrize(
    "dependencies, result",
    [
        ({}, False),
        ("DOWNLOAD", False),
        ([], False),
        (["DOWNLOAD"], True),
        (["BG_DOWNLOAD"], True),
        (["DOWNLOAD", "BG_DOWNLOAD"], True),
        (["DOWNLOAD", "DOWNLOAD"], True),
        (["OWNLAODER"], False),
    ],
)
def test__check_dane_dependencies(dependencies, result):
    assert __check_dane_dependencies(dependencies) == result


@pytest.mark.parametrize(
    "s, hash",
    [
        ("file.mp3", "906442a8f0c659227e6af143de05511545cbe0fd28385275ff0e4983"),
    ],
)
def test_hash_string(s, hash):
    assert hash_string(s) == hash
