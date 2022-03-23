#!/bin/sh

USE_VENV=$1 #any argument will trigger using the virtual env
SCRIPTPATH="$( cd "$(dirname "$0")" ; pwd -P )"

cd "$SCRIPTPATH"


if [ ! -z "$USE_VENV" ] ; then
	poetry shell
fi

cd ../

# test (configured in pyproject.toml)
pytest

# check lint rules (configured in .flake8)
flake8

# check formatting (configured in pyproject.toml)
black --check .

# static type check (configured in pyproject.toml)
mypy .
