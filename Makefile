.PHONY: all
all:

SHELL = /bin/bash

NAME := pydpkg
PYMAJOR := 3
PYREV := 10
PYPATCH := 0
PYVERSION := ${PYMAJOR}.${PYREV}.${PYPATCH}
PYENV := ~/.pyenv/versions/${PYVERSION}
VENV_NAME := ${NAME}-${PYVERSION}
VENV := ${PYENV}/envs/${VENV_NAME}
EGGLINK := ${VENV}/lib/python${PYMAJOR}.${PYREV}/site-packages/${NAME}.egg-link

# delberately smash this so we keep arm64-homebrew (/opt/homebrew) out of our field of view
export PATH = ${VENV}/bin:/usr/local/bin:/usr/local/sbin:/usr/bin:/bin:/usr/sbin:/sbin

uname_m := $(shell uname -m)
uname_s := $(shell uname -s)

ifeq ($(uname_s),Darwin)
  BREW_SSL := /usr/local/opt/openssl@1.1
  BREW_READLINE := /usr/local/opt/readline
  export LDFLAGS = -L${BREW_SSL}/lib -L${BREW_READLINE}/lib
  export CFLAGS = -I${BREW_SSL}/include -I${BREW_READLINE}/include
  export CPPFLAGS = -I${BREW_SSL}/include -I${BREW_READLINE}/include
  ${BREW_READLINE}:
	${ARCH_PREFIX} brew install readline
  ${BREW_SSL}:
	${ARCH_PREFIX} brew install openssl@1.1

  ifeq ($(uname_m),arm64)
    ARCH_PREFIX := arch -x86_64
  endif
else
  ${BREW_READLINE}: .PHONY
  ${BREW_SSL}: .PHONY
endif


${PYENV}: ${BREW_SSL} ${BREW_READLINE}
	${ARCH_PREFIX} pyenv install ${PYVERSION}

${VENV}: ${PYENV}
	${ARCH_PREFIX} pyenv virtualenv ${PYVERSION} ${VENV_NAME}
	${VENV}/bin/python -m pip install -U pip setuptools wheel
	${VENV}/bin/python -m pip install -U poetry

.python-version: ${VENV}
	echo ${VENV_NAME} >.python-version

poetry.lock:
	PYENV_VERSION=${NAME} VIRTUAL_ENV=${VENV} ${VENV}/bin/poetry lock

${EGGLINK}: poetry.lock
	PYENV_VERSION=${NAME} VIRTUAL_ENV=${VENV} ${VENV}/bin/poetry install
	# an update-install might not necessarily update this
	touch ${EGGLINK}

setup: .python-version ${EGGLINK}

clean:
	git clean -fdx -e '*.ipynb'

nuke:
	git clean -fdx -e '*.ipynb'
	rm -f .python-version
	pyenv uninstall -f ${VENV_NAME}

update: pyproject.toml
	PYENV_VERSION=${NAME} VIRTUAL_ENV=${VENV} ${VENV}/bin/poetry install
	PYENV_VERSION=${NAME} VIRTUAL_ENV=${VENV} ${VENV}/bin/poetry update

format: setup
	poetry run isort . && poetry run black .

format-check: setup
	poetry run isort --check . && poetry run black --check .

test: black pylint flakehell pycodestyle pytest
	@echo "Running all tests"

pytest: setup
	@echo "Running unit tests"
	poetry run pytest -p no:warnings tests

black: setup
	@echo "Checking code formatting and imports..."
	poetry run black --check .

pylint: setup
	@echo "Linting code style with pylint..."
	poetry run pylint -d R0912 -d W0511 ${NAME}

flakehell: setup
	@echo "Linting code style with flakehell..."
	poetry run flakehell lint ${NAME} test

pycodestyle: setup
	@echo "Linting codestyle with pycodestyle (formerly pep8)"
	# ignore E203 because pep8 and black disagree about whitespace before ':'
	poetry run pycodestyle --max-line-length=120 --ignore=E203 ${NAME}

install: setup

est:
	@echo 'I am loved, I am valued, I am giving the Foundation fifteen thousand dollars.'
