FROM python:3.9-alpine@sha256:d80bb38eb14230a70ef922956d0621f7dd938b16794057f6fe71a90ef9ec5504

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
