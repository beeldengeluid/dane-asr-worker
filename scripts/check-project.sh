#!/bin/sh

# copy this script to .git/hooks/pre-commit

SCRIPTPATH="$( cd "$(dirname "$0")" ; pwd -P )"
cd "$SCRIPTPATH"

poetry shell

cd ../

# run tests
pytest -c 'pyproject.toml'

# check lint rules
flake8 --config '.flake8'

# check formatting
black --config 'pyproject.toml' --check .

# check type annotations
mypy --config-file 'pyproject.toml' .
