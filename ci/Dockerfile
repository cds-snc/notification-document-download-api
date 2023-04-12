FROM python:3.10-alpine3.16@sha256:b2d1f7c5ef2aad57f135104240e91c5327d9c414a58517f1080d55ed6a7a591d

ENV PYTHONDONTWRITEBYTECODE 1
ARG POETRY_VERSION="1.3.2"
ENV POETRY_VIRTUALENVS_CREATE false

RUN apk add --no-cache build-base git gcc make libffi-dev openssl-dev libmagic && rm -rf /var/cache/apk/*

RUN pip3 install poetry==${POETRY_VERSION} \
  && poetry --version

RUN set -ex && mkdir /app

WORKDIR /app

COPY . /app

RUN poetry add wheel

RUN set -ex && poetry install

ENV PORT=7000

CMD ["sh", "-c", "gunicorn -c gunicorn_config.py application"]
