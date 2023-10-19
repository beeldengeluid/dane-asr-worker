#!/bin/sh

echo python is located here: `which python`
echo python3 is located here: `which python3`
echo poetry is located here: `which poetry`
echo virtualenv is in: `poetry env info --path`

echo "Now starting the worker"
poetry run python3 worker.py

echo worker crashed, tailing /dev/null for debugging
tail -f /dev/null