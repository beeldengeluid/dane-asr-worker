import pytest
from yacs.config import CfgNode

from base_util import __check_dane_dependencies, validate_config


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
