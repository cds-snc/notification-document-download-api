FROM mcr.microsoft.com/vscode/devcontainers/python:1-3.12

ENV POETRY_VERSION="1.7.1"

RUN apt-get update \
    && apt-get -y install --no-install-recommends apt-utils 2>&1 \
    && apt-get -y install \
        curl \
        emacs \
        exa \
        fd-find \
        fzf \
        git \
        iproute2 \
        iputils-ping \
        less \
        libmagic-dev \
        libsodium-dev \
        lsb-release \
        man-db \
        manpages \
        net-tools \
        nodejs \
        npm \
        openssh-client \
        procps \
        ripgrep \
        sudo \
        tldr \
        unzip \
        vim \
    && apt-get autoremove -y \
    && apt-get clean -y \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --upgrade pip

COPY .devcontainer/scripts/notify-dev-entrypoint.sh /usr/local/bin/

ENV SHELL /bin/zsh

EXPOSE 7000
