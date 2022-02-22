import json

from DANE import Document, Result, Task
import pytest

from worker import AsrWorker

DUMMY_FILE_PATH = "path/to/download/file.mp3"
DUMMY_DANE_DIRS = {
    "TEMP_FOLDER": "/mnt/dane-fs/input-dir",
    "OUT_FOLDER": "/mnt/dane-fs/output-dir",
}
DUMMY_DOC = Document.from_json(
    json.dumps(
        {
            "target": {
                "id": "dummy_id_12345",
                "url": "http://dummy-url.com/dummy.mp3",
                "type": "Video",
            },
            "creator": {"id": "UNIT TEST", "type": "Organization"},
            "_id": "dummy-uuid-12345-43214",
        }
    )
)
DUMMY_TASK = Task.from_json(
    {"key": "ASR", "state": 201, "msg": "Queued", "priority": 1}
)
DUMMY_RESULT = Result.from_json(
    json.dumps(
        {
            "generator": {
                "id": "dummy-id-12345",
                "type": "Software",
                "name": "ASR",
                "homepage": "git@github.com:beeldengeluid/dane-asr-worker.git",
            },
            "payload": {"TODO": "TODO"},
        }
    )
)

"""----------------------------------ID MANAGEMENT FUNCTIONS ---------------------------------"""


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
def test_get_asset_id(config, input_file, asset_id):
    w = AsrWorker(config)
    assert w.get_asset_id(input_file) == asset_id


@pytest.mark.parametrize(
    "s, hash",
    [
        ("file.mp3", "906442a8f0c659227e6af143de05511545cbe0fd28385275ff0e4983"),
    ],
)
def test_hash_string(config, s, hash):
    w = AsrWorker(config)
    assert w.hash_string(s) == hash
