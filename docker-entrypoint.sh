#!/bin/sh

echo "Starting virtual env and DANE ASR worker"

# poetry shell is no good, because we do not want an interactive shell
# https://github.com/orgs/python-poetry/discussions/3526
. $(poetry env info --path)/bin/activate

echo "Now starting the worker"

python ./worker.py

# NOTE somehow does not work in OpenShift
# poetry run python worker.py