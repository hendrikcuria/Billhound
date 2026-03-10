.PHONY: run test lint migrate db-up db-down

run:
	python -m src.main

test:
	pytest tests/ -v

lint:
	ruff check src/ tests/
	mypy src/

migrate:
	alembic revision --autogenerate -m "$(msg)"

upgrade:
	alembic upgrade head

db-up:
	docker-compose up -d

db-down:
	docker-compose down

coverage:
	coverage run -m pytest tests/ -v
	coverage report -m
