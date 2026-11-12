# Contact Explorer — Developer Tasks Automation Makefile
.PHONY: help install dev test lint format clean run serve benchmark seed

help:
	@echo "Contact Explorer Developer Commands:"
	@echo "  make install   - Install package in standard mode"
	@echo "  make dev       - Install package in editable mode with development dependencies"
	@echo "  make test      - Run automated pytest suite with coverage"
	@echo "  make lint      - Run Ruff and Mypy checks"
	@echo "  make format    - Automatically format code with Ruff"
	@echo "  make run       - Launch the desktop Tkinter application"
	@echo "  make serve     - Run the headless HTTP REST API server"
	@echo "  make seed      - Populate the local database with demo records"
	@echo "  make benchmark - Run bulk insert and search benchmarks"
	@echo "  make clean     - Clean build artifacts, pycache, and test caches"

install:
	pip install .

dev:
	pip install --upgrade pip
	pip install -e ".[dev]"

test:
	pytest -v --cov=contact_explorer --cov-report=term-missing

lint:
	ruff check .
	mypy contact_explorer

format:
	ruff format .
	ruff check . --fix

run:
	python run.py

serve:
	python serve.py

seed:
	python scripts/seed_demo_data.py

benchmark:
	python scripts/benchmark.py --count 500

clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache/ .coverage htmlcov/ .mypy_cache/ .ruff_cache/
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.py[cod]" -delete
