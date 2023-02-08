# Makefile

.PHONY: setup
setup:
	. venv/bin/activate && pip install -e .[dev]

.PHONY: format
format:
	. venv/bin/activate && black src/topbid/ tests/

.PHONY: lint
lint:
	. venv/bin/activate && pylint src/topbid/ tests/

.PHONY: test
test:
	. venv/bin/activate && pytest tests/

.PHONY: build
build:
	. venv/bin/activate && python -m build

.PHONY: publish-test
publish-test:
	. venv/bin/activate && python -m twine upload --repository-url https://test.pypi.org/legacy/ dist/*

.PHONY: publish
publish:
	. venv/bin/activate && python -m twine upload dist/*
