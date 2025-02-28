#!/bin/bash
set -ex

###################################################################
# This script will get executed *once* the Docker container has
# been built. Commands that need to be executed with all available
# tools and the filesystem mount enabled should be located here.
###################################################################

# Define aliases
echo -e "\n\n# User's Aliases" >> ~/.zshrc
echo -e "alias fd=fdfind" >> ~/.zshrc
echo -e "alias l='ls -al --color'" >> ~/.zshrc
echo -e "alias ls='exa'" >> ~/.zshrc
echo -e "alias l='exa -alh'" >> ~/.zshrc
echo -e "alias ll='exa -alh@ --git'" >> ~/.zshrc
echo -e "alias lt='exa -al -T -L 2'" >> ~/.zshrc
echo -e "alias poe='poetry run poe'" >> ~/.zshrc

echo -e "# fzf key bindings and completion" >> ~/.zshrc
echo -e "source /usr/share/doc/fzf/examples/key-bindings.zsh" >> ~/.zshrc
echo -e "source /usr/share/doc/fzf/examples/completion.zsh" >> ~/.zshrc

# Poetry autocomplete
echo -e "fpath+=/.zfunc" >> ~/.zshrc
echo -e "autoload -Uz compinit && compinit"

pip install poetry=="${POETRY_VERSION}"  poetry-plugin-sort \
  && poetry --version

# Disable poetry auto-venv creation
poetry config virtualenvs.create false

  # Initialize poetry autocompletions
mkdir ~/.zfunc
touch ~/.zfunc/_poetry
poetry completions zsh > ~/.zfunc/_poetry

# Manually create and activate a virtual environment with a static path
python -m venv "${POETRY_VENV_PATH}"
source "${POETRY_VENV_PATH}/bin/activate"

# Ensure newly created shells activate the poetry venv
echo "source ${POETRY_VENV_PATH}/bin/activate" >> ~/.zshrc

# Set up git blame to ignore certain revisions e.g. sweeping code formatting changes.
git config blame.ignoreRevsFile .git-blame-ignore-revs

poetry install

# Poe the Poet plugin tab completions
touch ~/.zfunc/_poe
poetry run poe _zsh_completion > ~/.zfunc/_poe

