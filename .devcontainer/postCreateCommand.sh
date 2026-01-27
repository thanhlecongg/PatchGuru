#! /usr/bin/env bash

# Install Dependencies
poetry lock
poetry install --with dev

# Install pre-commit hooks
poetry run pre-commit install --install-hooks


# Please uncomment the following lines if you want to set up the other target projects as well
bash .devcontainer/setup_marshmallow.sh
# bash .devcontainer/setup_scipy.sh
# bash .devcontainer/setup_keras.sh
# bash .devcontainer/setup_pandas.sh

