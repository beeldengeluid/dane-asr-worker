import pytest
from io_util import get_asset_id


@pytest.mark.parametrize(
    "input_file, asset_id",
    [
        ("/path/to/download/file.mp3", "file"),
        ("/path/with/extra//file.mp3", "file"),
        ("~/relative/path/file.mp3", "file"),
        (
            "/path/to/download/file.with.many.extensions.mp3",
            "file.with.many.extensions",
        ),
    ],
)
def test_get_asset_id(input_file, asset_id):
    assert get_asset_id(input_file) == asset_id
