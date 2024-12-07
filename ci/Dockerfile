FROM python:3.12-alpine3.20@sha256:bb94273467caf397de28b4e6dd09ca4a2dd1b53fa9b130d5b2c7c82719258356

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
