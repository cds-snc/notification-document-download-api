FROM mcr.microsoft.com/vscode/devcontainers/python:1-3.12@sha256:7876580dc67fd460fd962f004cbeb480027e9bbc0657096f1087db11f9eaff39

ENV POETRY_VERSION="1.7.1"
ENV POETRY_VENV_PATH="/home/vscode/.venv/workspace"

# Base image is frozen upstream and its Yarn apt repo key has expired; drop that source so apt works
RUN rm -f /etc/apt/sources.list.d/yarn.list \
    && apt-get update \
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
    # CVE-2026-111497: base image ships vulnerable libbrotli1; pull fixed build from bookworm-security
    && apt-get -y install --only-upgrade libbrotli1 libbrotli-dev \
    && apt-get autoremove -y \
    && apt-get clean -y \
    && rm -rf /var/lib/apt/lists/*

# ca-certificates >= 20250419~deb12u2 (bookworm-security) removes emSign ECC Root CA - G3 and Comodo AAA Services root
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --upgrade pip

COPY .devcontainer/scripts/notify-dev-entrypoint.sh /usr/local/bin/

ENV SHELL /bin/zsh

EXPOSE 7000
