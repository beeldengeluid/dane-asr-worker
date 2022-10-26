from enum import Enum
from typing import Dict, Any


class APIResponse(Enum):

    ASR_SUCCESS: Dict[str, Any] = {
        "state": 200,
        "message": "ASR finished successfully",
        "finished": True,
    }
    ASR_INPUT_UNACCEPTABLE: Dict[str, Any] = {
        "state": 406,
        "message": "Not acceptable, accepted file formats are; mov,mp4,m4a,3gp,3g2,mj2",
    }
    ASR_FAILED: Dict[str, Any] = {
        "state": 500,
        "message": "Something went wrong when encoding the file",
    }
    ASR_OUTPUT_CORRUPT: Dict[str, Any] = {
        "state": 500,
        "message": "ASR output did not yield a transcript file",
    }

    FILE_NOT_FOUND: Dict[str, Any] = {"state": 404, "message": "File not found"}

    PID_FILE_CORRUPTED: Dict[str, Any] = {
        "state": 500,
        "message": "PID file was corrupted",
    }
    PID_NOT_FOUND: Dict[str, Any] = {
        "state": 404,
        "message": "Error: PID does not exist (anymore)",
    }

    SIMULATION_IN_PROGRESS: Dict[str, Any] = {
        "state": 200,
        "message": "Simulation in progress",
    }

    TRANSCODE_FAILED: Dict[str, Any] = {
        "state": 500,
        "message": "Transcoding of input to mp3 failed",
    }
