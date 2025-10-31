PYTHON=python

.PHONY: lint test migrate

lint:
flake8 .

migrate:
alembic upgrade head

test: migrate
pytest
