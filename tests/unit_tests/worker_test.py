import json
from DANE import Result, Document, Task

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
            "payload": {
                "TODO" : "TODO"
            },
        }
    )
)
