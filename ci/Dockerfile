FROM python:3.12-alpine3.24@sha256:5789aa194f757888f41fa3d48e14b6feaa1b57c0af0b56fcb1372d6474d3bff0

ENV PYTHONDONTWRITEBYTECODE 1
ARG POETRY_VERSION="1.7.1"
ENV POETRY_VIRTUALENVS_CREATE false

RUN apk add --no-cache build-base git gcc make libffi-dev openssl-dev libmagic rust cargo && rm -rf /var/cache/apk/*

# -- Install CA certificates and update them to disable emSign ECC Root CA - G3 --
RUN apk add --no-cache ca-certificates && \
    sed -i \
      -e 's|^mozilla/emSign_ECC_Root_CA_-_G3.crt|!&|' \
      -e 's|^mozilla/Comodo_AAA_Services_root.crt|!&|' \
      /etc/ca-certificates.conf && \
    update-ca-certificates --fresh

RUN pip3 install poetry==${POETRY_VERSION} \
  && poetry --version

RUN set -ex && mkdir /app

WORKDIR /app

COPY . /app

RUN poetry add wheel

RUN set -ex && poetry install

ENV PORT=7000

CMD ["sh", "-c", "gunicorn -c gunicorn_config.py application"]
