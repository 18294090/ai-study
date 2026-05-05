.PHONY: install dev test lint format clean backup eval eval-sample

# Python backend
BACKEND=backend
POETRY=$(shell which poetry 2>/dev/null || echo "pip install poetry && poetry")

# Default target
all: install

# Install dependencies
install:
	@echo "Installing backend dependencies..."
	cd $(BACKEND) && poetry install
	@echo "Done! Activate with: poetry shell"

# Development mode
dev:
	@echo "Starting backend in dev mode..."
	cd $(BACKEND) && poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
test:
	@echo "Running tests..."
	cd $(BACKEND) && poetry run pytest -v

# Lint
lint:
	@echo "Running lint..."
	cd $(BACKEND) && poetry run ruff check app/

# Format code
format:
	@echo "Formatting code..."
	cd $(BACKEND) && poetry run ruff format app/

# Clean cache
clean:
	@echo "Cleaning cache files..."
	find $(BACKEND) -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find $(BACKEND) -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find $(BACKEND) -type f -name "*.pyc" -delete 2>/dev/null || true

# Database migrations
migrate:
	@echo "Running migrations..."
	cd $(BACKEND) && poetry run alembic upgrade head

# Create migration
migration:
	@echo "Creating migration..."
	cd $(BACKEND) && poetry run alembic revision --autogenerate -m "$(NAME)"

# Shell
shell:
	cd $(BACKEND) && poetry run python

# Backend status
status:
	@echo "=== Backend Status ==="
	@cd $(BACKEND) && poetry show -- tree 2>/dev/null || poetry show

# Run evaluation
eval:
	@echo "Running KG triple evaluation..."
	@cd backend && python3 -c "
import sys
sys.path.insert(0, 'app/kg')
from src.eval.runner import run_eval

def extractor(text):
    return []

result = run_eval(
    extractor=extractor,
    dataset_path='data/eval/kg_triples_sample.jsonl'
)
metrics = result['metrics']
print(f'Metrics: {metrics}')
"

eval-sample:
	@echo "Sample evaluation dataset location: backend/data/eval/"
	@cd backend && python3 -c "import json; f=open('data/eval/kg_triples_sample.jsonl'); print(f'Entries: {len(f.readlines())}')"

# Help
help:
	@echo "Available targets:"
	@echo "  install  - Install dependencies (poetry)"
	@echo "  dev      - Run development server"
	@echo "  test     - Run tests"
	@echo "  lint     - Run linter"
	@echo "  format   - Format code"
	@echo "  clean    - Clean cache files"
	@echo "  migrate  - Run database migrations"
	@echo "  shell    - Open Python shell"
	@echo "  status   - Show installed packages"
	@echo "  help     - Show this help"
