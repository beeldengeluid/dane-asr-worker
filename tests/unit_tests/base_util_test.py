from mockito import unstub
from base_util import validate_config

def test_validate_config(config, environment_variables):
    try:
        assert validate_config(config, False)
    finally:
        unstub()
