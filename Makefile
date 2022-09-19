.PHONY: all
all:

SHELL = /bin/bash

NAME := pydpkg
PYMAJOR := 3
PYREV := 10
PYPATCH := 7
PYVERSION := ${PYMAJOR}.${PYREV}.${PYPATCH}
PYENV := ${HOME}/.pyenv/versions/${PYVERSION}
VENV_NAME := ${NAME}-${PYVERSION}
VENV := ${PYENV}/envs/${VENV_NAME}
PYTHON_BIN := ${VENV}/bin/python
POETRY_BIN := ${VENV}/bin/poetry
EGGLINK := ${VENV}/lib/python${PYMAJOR}.${PYREV}/site-packages/${NAME}.egg-link
export VIRTUAL_ENV := ${VENV}
export PYENV_VERSION := ${VENV_NAME}

# delberately smash this so we keep arm64-homebrew (/opt/homebrew) out of our field of view
export PATH = ${VENV}/bin:/usr/local/bin:/usr/local/sbin:/usr/bin:/bin:/usr/sbin:/sbin

uname_m := $(shell uname -m)
uname_s := $(shell uname -s)

ifeq ($(uname_s),Darwin)
  PYENV_BIN := /usr/local/bin/pyenv
  BREW_SSL := /usr/local/opt/openssl@1.1
  BREW_READLINE := /usr/local/opt/readline
  export LDFLAGS = -L${BREW_SSL}/lib -L${BREW_READLINE}/lib
  export CFLAGS = -I${BREW_SSL}/include -I${BREW_READLINE}/include
  export CPPFLAGS = -I${BREW_SSL}/include -I${BREW_READLINE}/include

  ifeq ($(uname_m),arm64)
    ARCH_PREFIX := arch -x86_64
  endif

  ${BREW_READLINE}:
	${ARCH_PREFIX} brew install readline

  ${BREW_SSL}:
	${ARCH_PREFIX} brew install openssl@1.1
else
  PYENV_BIN := ${HOME}/.pyenv/bin/pyenv
  ${BREW_READLINE}: .PHONY
  ${BREW_SSL}: .PHONY
endif

${PYENV}: ${BREW_SSL} ${BREW_READLINE} ${PYENV_BIN}
	${ARCH_PREFIX} ${PYENV_BIN} install -s ${PYVERSION}

${VENV}: ${PYENV}
	${ARCH_PREFIX} ${PYENV_BIN} virtualenv ${PYVERSION} ${VENV_NAME}
	${ARCH_PREFIX} ${PYTHON_BIN} -m pip install -U pip setuptools wheel
	${ARCH_PREFIX} ${PYTHON_BIN} -m pip install -U poetry
	${ARCH_PREFIX} ${POETRY_BIN} config virtualenvs.create false --local
	${ARCH_PREFIX} ${POETRY_BIN} config virtualenvs.in-project false --local

.python-version: ${VENV}
	echo ${PYVERSION}/envs/${VENV_NAME} >.python-version

poetry.lock:
	${ARCH_PREFIX} ${POETRY_BIN} lock

${EGGLINK}: poetry.lock
	${ARCH_PREFIX} ${POETRY_BIN} install
	touch ${EGGLINK}

setup: .python-version ${EGGLINK}

clean:
	git clean -fdx -e '*.ipynb'

nuke:
	git clean -fdx -e '*.ipynb'
	rm -f .python-version
	${ARCH_PREFIX} ${PYENV_BIN} uninstall -f ${PYVERSION}/envs/${VENV_NAME}

update: pyproject.toml
	${ARCH_PREFIX} ${POETRY_BIN} lock
	${ARCH_PREFIX} ${POETRY_BIN} install
	${ARCH_PREFIX} ${POETRY_BIN} update

format: setup
	${ARCH_PREFIX} ${POETRY_BIN} run isort . && poetry run black .

format-check: setup
	${ARCH_PREFIX} ${POETRY_BIN} run isort --check . && poetry run black --check .

test: black pylint flakeheaven pycodestyle pytest
	@echo "Running all tests"

pytest: setup
	@echo "Running unit tests"
	${ARCH_PREFIX} ${POETRY_BIN} run pytest -p no:warnings tests

black: setup
	@echo "Checking code formatting and imports..."
	${ARCH_PREFIX} ${POETRY_BIN} run black --check .

pylint: setup
	@echo "Linting code style with pylint..."
	${ARCH_PREFIX} ${POETRY_BIN} run pylint -d R0912 -d W0511 ${NAME}

flakeheaven: setup
	@echo "Linting code style with flakeheaven..."
	${ARCH_PREFIX} ${POETRY_BIN} run flakeheaven lint ${NAME} test

pycodestyle: setup
	@echo "Linting codestyle with pycodestyle (formerly pep8)"
	@# ignore E203 because pep8 and black disagree about whitespace before ':'
	${ARCH_PREFIX} ${POETRY_BIN} run pycodestyle --max-line-length=120 --ignore=E203 ${NAME}

install: setup

est:
	@echo 'I am loved, I am valued, I am giving the Foundation fifteen thousand dollars.'
