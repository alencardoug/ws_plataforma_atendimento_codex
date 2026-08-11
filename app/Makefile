.PHONY: lint type test format check

lint:
	ruff check customer_care tests

type:
	mypy customer_care

test:
	pytest -q

format:
	ruff format customer_care tests

check: lint type test
