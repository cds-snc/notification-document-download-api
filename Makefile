SHELL := /bin/bash

GIT_COMMIT ?= $(shell git rev-parse HEAD)

.PHONY: run
run:
	FLASK_APP=application.py FLASK_ENV=development poetry run flask run -p 7000

.PHONY: test
test:
	poetry run ruff check --select I .
	poetry run mypy .
	poetry run py.test --cov=app --cov-report=term-missing tests/

.PHONY: freeze-requirements
freeze-requirements:
	poetry lock --no-update

.PHONY: test-requirements
test-requirements:
	poetry check --lock

.PHONY: format
format:
	ruff check --select I --fix .
	ruff check
	ruff format .