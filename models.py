from dataclasses import dataclass
from typing import TypedDict


@dataclass
class ASRProvenance:
    asr_processing_time: float  # retrieved via submit_asr_job()
    download_time: float  # retrieved via dane-beng-download-worker or download_content()
    kaldi_nl_version: str = "Kaldi-NL v0.4.1"  # default for now
    kaldi_nl_git_url: str = (
        "https://github.com/opensource-spraakherkenning-nl/Kaldi_NL"  # default for now
    )

    def to_json(self):
        return {
            "asr_processing_time": self.asr_processing_time,
            "download_time": self.download_time,
            "kaldi_nl_version": self.kaldi_nl_version,
            "kaldi_nl_git_url": self.kaldi_nl_git_url,
        }


# NOTE copied from dane-beng-download-worker (move this to DANE later)
@dataclass
class DownloadResult:
    file_path: str  # target_file_path,  # TODO harmonize with dane-download-worker
    download_time: float = -1  # time (secs) taken to receive data after request
    mime_type: str = "unknown"  # download_data.get("mime_type", "unknown"),
    content_length: int = -1  # download_data.get("content_length", -1),


# returned by callback()
class CallbackResponse(TypedDict):
    state: int
    message: str
