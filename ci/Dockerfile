FROM python:3.10-alpine

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
