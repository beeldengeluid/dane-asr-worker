import pytest
import os


@pytest.fixture(scope="session")
def config():
    from DANE.config import cfg

    return cfg


@pytest.fixture(scope="session")
def environment_variables():  # TODO migrate secrets from config.yml to env
    os.environ["DW_ASR_UNIT_TESTING"] = "true"