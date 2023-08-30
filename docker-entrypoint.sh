#!/bin/sh

echo "Starting virtual env and DANE ASR worker"

poetry shell

echo "Now starting the worker"

python ./worker.py