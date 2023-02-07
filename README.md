# document-download-api
Document Download API


# install steps:

### the docker way
```bash
make build-with-docker
docker run make run
```

### the local way
```bash
brew install libmagic poetry
poetry install
make run
```

## Updating application dependencies

`poetry.lock` file is generated from the `pyproject.toml` in order to pin
versions of all nested dependencies. If `pyproject.toml` has been changed (or
we want to update the unpinned nested dependencies) `poetry.lock` should be
regenerated with

```
poetry lock --no-update
```

`poetry.lock` should be committed alongside `pyproject.toml` changes.
