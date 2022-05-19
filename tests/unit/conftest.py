import os
import pytest
from yacs.config import CfgNode


@pytest.fixture(scope="session")
def config() -> CfgNode:
    from dane.config import cfg

    return cfg


@pytest.fixture(scope="session")
def environment_variables():  # TODO migrate secrets from config.yml to env
    os.environ["DW_ASR_UNIT_TESTING"] = "true"
