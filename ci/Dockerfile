FROM python:3.10-alpine3.16@sha256:923d30cb18f3d67160cb055a3c3862771edc5d07c63d54d9ca144954c3a6bdfe

ENV PYTHONDONTWRITEBYTECODE 1
ARG POETRY_VERSION="1.3.2"

RUN apk add --no-cache build-base git gcc make libffi-dev openssl-dev libmagic && rm -rf /var/cache/apk/*

RUN pip3 install poetry==${POETRY_VERSION} \
  && poetry --version

RUN set -ex && mkdir /app

WORKDIR /app

COPY . /app

# update pip
RUN poetry add wheel

RUN set -ex && poetry install

ENV PORT=7000

CMD ["sh", "-c", "gunicorn -c gunicorn_config.py application"]
