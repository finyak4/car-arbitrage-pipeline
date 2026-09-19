# .PHONY tells Make these are command names, not actual file names
.PHONY: install setup discover_selected retrieve_data clean

# Installs everything in your pyproject.toml into your active conda/venv
install:
	pip install -e ".[dev]"
	playwright install chromium

# Sets up your SQLite database
setup:
	python -m src.cli init_db

discover:
	python -m src.cli discover

retrieve_data:
	python -m src.cli retrieve_data

clean:
	python -m src.cli clean_data


# --------------Quality Assurance-------------------
format:
	ruff format src tests
	ruff check --fix src tests

lint:
	ruff check src tests
	mypy src
	bandit -r src/ -ll

# test:
# 	pytest tests/ -v