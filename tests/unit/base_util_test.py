from yacs.config import CfgNode

from base_util import validate_config


def test_validate_config(config: CfgNode, environment_variables):
    assert validate_config(config, False)
