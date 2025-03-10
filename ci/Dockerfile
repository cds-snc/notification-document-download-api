FROM python:3.12-alpine3.20@sha256:4ce45e8acd11d49ee07aa736cd7ca2950df75033b946f3a5d9eca1cb4aae2ab7

ENV PYTHONDONTWRITEBYTECODE 1
ARG POETRY_VERSION="1.7.1"
ENV POETRY_VIRTUALENVS_CREATE false

RUN apk add --no-cache build-base git gcc make libffi-dev openssl-dev libmagic rust cargo && rm -rf /var/cache/apk/*

RUN pip3 install poetry==${POETRY_VERSION} \
  && poetry --version

RUN set -ex && mkdir /app

WORKDIR /app

COPY . /app

RUN poetry add wheel

RUN set -ex && poetry install

ENV PORT=7000

CMD ["sh", "-c", "gunicorn -c gunicorn_config.py application"]
