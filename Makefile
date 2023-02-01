SHELL := /bin/bash

GIT_COMMIT ?= $(shell git rev-parse HEAD)

.PHONY: run
run:
	FLASK_APP=application.py FLASK_ENV=development poetry run flask run -p 7000

.PHONY: test
test:
	py.test --cov=app --cov-report=term-missing tests/
	flake8 .

.PHONY: format
format:
	black .
