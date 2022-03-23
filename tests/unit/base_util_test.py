from base_util import validate_config


def test_validate_config(config, environment_variables):
    assert validate_config(config, False)
