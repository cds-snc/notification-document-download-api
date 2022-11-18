FROM python:3.9-alpine@sha256:ea679ee27dbb8f36fbfc304be1b488b4fd7bea95dd230a47f97187c2e3fd4807

ENV PYTHONDONTWRITEBYTECODE 1

RUN apk add --no-cache build-base git gcc make libffi-dev openssl-dev libmagic && rm -rf /var/cache/apk/*

# update pip
RUN python -m pip install wheel

RUN set -ex && mkdir /app

WORKDIR /app

COPY . /app

RUN set -ex && pip3 install -r requirements.txt

ENV PORT=7000

CMD ["sh", "-c", "gunicorn -c gunicorn_config.py application"]
