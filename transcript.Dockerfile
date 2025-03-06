FROM docker.io/python:3.11-slim-bookworm

#COPY ./tests/data/asr_output/BG27239MPG_-HRE000033CB ./tests/data/asr_output/BG27239MPG_-HRE000033CB
COPY transcript_atom.py /transcript_atom.py

ARG ASR_OUTPUT_DIR
ARG JSON_OUTPUT_DIR

ENTRYPOINT ["python","transcript_atom.py"]
CMD [ASR_OUTPUT_DIR, JSON_OUTPUT_DIR]