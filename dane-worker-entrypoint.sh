#!/bin/sh

echo "Now starting the worker"
poetry run python3 main.py "$@"