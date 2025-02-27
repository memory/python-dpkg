.PHONY: all
all:

SHELL = /bin/bash

CYAN=\033[0;36m
RED=\033[0;31m
ORANGE=\033[38;5;208m
WHITE=\033[1;37m
RST=\033[0m

NAME := pydpkg
PYMAJOR := 3
PYREV := 13
PYPATCH := 2
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
  BREW_READLINE := /usr/local/opt/readline
  export LDFLAGS = -L${BREW_READLINE}/lib
  export CFLAGS = -I${BREW_READLINE}/include
  export CPPFLAGS = -I${BREW_READLINE}/include

  ifeq ($(uname_m),arm64)
    ARCH_PREFIX := arch -x86_64
  endif

  ${BREW_READLINE}:
	${ARCH_PREFIX} brew install readline
else
  PYENV_BIN := ${HOME}/.pyenv/bin/pyenv
  ${BREW_READLINE}: .PHONY
endif

${PYENV}: ${BREW_READLINE} ${PYENV_BIN}
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
	@echo -e "${ORANGE}*** Removing untracked files with git-clean --fdx!${RST}"
	git clean -fdx -e '*.ipynb'

nuke: clean
	@echo -e "${RED}*** Nuking your virtualenv: ${WHITE}${VENV_NAME}${RST}"
	rm -f .python-version
	${PYENV_BIN} uninstall -f ${VENV_NAME}
	rm -rf ${VENV}

# usually there's no reason to uninstall python itself, and reinstalling
# it is so very very slow
tacnuke: nuke
	@echo -e "${RED}*** Nuking your python distribution to bedrock: ${WHITE}${PYVERSION}${RST}"
	${PYENV_BIN} uninstall -f ${PYVERSION}

update: pyproject.toml
	${ARCH_PREFIX} ${POETRY_BIN} lock
	${ARCH_PREFIX} ${POETRY_BIN} install
	${ARCH_PREFIX} ${POETRY_BIN} update

format: setup
	${ARCH_PREFIX} ${POETRY_BIN} run ruff format

format-check: setup
	${ARCH_PREFIX} ${POETRY_BIN} run ruff format --check

pytest: setup
	@echo "Running unit tests"
	${ARCH_PREFIX} ${POETRY_BIN} run pytest -p no:warnings tests

ruff: setup
	@echo "Linting code style with ruff..."
	${ARCH_PREFIX} ${POETRY_BIN} run ruff check

test: ruff pytest
	@echo "Running all tests"

install: setup

est:
	@echo 'I am loved, I am valued, I am giving the Foundation fifteen thousand dollars.'
