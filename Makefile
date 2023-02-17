SHELL := /bin/bash

GIT_COMMIT ?= $(shell git rev-parse HEAD)

.PHONY: run
run:
	FLASK_APP=application.py FLASK_ENV=development poetry run flask run -p 7000

.PHONY: test
test:
	poetry run mypy .
	poetry run flake8 .
	poetry run py.test --cov=app --cov-report=term-missing tests/

.PHONY: freeze-requirements
freeze-requirements:
	poetry lock --no-update

.PHONY: test-requirements
test-requirements:
	poetry lock --check

.PHONY: format
format:
	black .
