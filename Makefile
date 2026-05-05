.PHONY: all install dev test lint format clean backup eval eval-sample migrate migration shell status help ensure-poetry

# Python backend
BACKEND=backend
POETRY_VENV=$(CURDIR)/.poetry-venv
POETRY=$(POETRY_VENV)/bin/poetry

# CUDA version (default: cu124 for CUDA 12.4)
# Override with: make install CUDA_VERSION=cu118
CUDA_VERSION ?= cu124

# Pip mirrors (domestic for speed)
PIP_INDEX        = https://pypi.tuna.tsinghua.edu.cn/simple
PIP_EXTRA_INDEX  = https://download.pytorch.org/whl/$(CUDA_VERSION)

# Default target
all: install

# Ensure Poetry is available (without relying on poetry being on PATH)
ensure-poetry:
	@if [ ! -x "$(POETRY)" ]; then \
		echo "Poetry not found, bootstrapping local toolchain in $(POETRY_VENV)..."; \
		rm -rf "$(POETRY_VENV)"; \
		python3 -m venv "$(POETRY_VENV)"; \
		SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
		REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
		PIP_CERT=/etc/ssl/certs/ca-certificates.crt \
		"$(POETRY_VENV)/bin/pip" install --quiet --upgrade pip -i $(PIP_INDEX); \
		SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
		REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
		PIP_CERT=/etc/ssl/certs/ca-certificates.crt \
		"$(POETRY_VENV)/bin/pip" install --quiet poetry -i $(PIP_INDEX); \
	fi

# Install dependencies (default: CUDA $(CUDA_VERSION))
# For CPU-only: make install CUDA_VERSION=cpu
install: ensure-poetry
	@echo "Installing backend dependencies (CUDA=$(CUDA_VERSION))..."
	@cd $(BACKEND) && \
	$(POETRY) config installer.max-workers 10 && \
	$(POETRY) config repositories.pytorch-cuda https://download.pytorch.org/whl/$(CUDA_VERSION) && \
	for i in 1 2 3; do \
		echo "Poetry install attempt $$i/3 (CUDA=$(CUDA_VERSION))..."; \
		PIP_INDEX_URL=$(PIP_INDEX) \
		PIP_EXTRA_INDEX_URL=$(PIP_EXTRA_INDEX) \
		PIP_DEFAULT_TIMEOUT=300 \
		POETRY_REQUESTS_TIMEOUT=300 \
		$(POETRY) install --no-interaction && exit 0; \
		echo "Attempt $$i failed, retrying..."; \
	done; \
	echo "Failed after 3 attempts. Try: make install CUDA_VERSION=cpu"; \
	exit 1
	@echo "Done! CUDA=$(CUDA_VERSION). Activate: $(POETRY) shell"

# Development mode
dev: ensure-poetry
	@echo "Starting backend in dev mode..."
	cd $(BACKEND) && $(POETRY) run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
test: ensure-poetry
	@echo "Running tests..."
	cd $(BACKEND) && $(POETRY) run pytest -v

# Lint
lint: ensure-poetry
	@echo "Running lint..."
	cd $(BACKEND) && $(POETRY) run ruff check app/

# Format code
format: ensure-poetry
	@echo "Formatting code..."
	cd $(BACKEND) && $(POETRY) run ruff format app/

# Clean cache
clean:
	@echo "Cleaning cache files..."
	find $(BACKEND) -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find $(BACKEND) -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find $(BACKEND) -type f -name "*.pyc" -delete 2>/dev/null || true

# Database migrations
migrate: ensure-poetry
	@echo "Running migrations..."
	cd $(BACKEND) && $(POETRY) run alembic upgrade head

# Create migration
migration: ensure-poetry
	@echo "Creating migration..."
	cd $(BACKEND) && $(POETRY) run alembic revision --autogenerate -m "$(NAME)"

# Shell
shell: ensure-poetry
	cd $(BACKEND) && $(POETRY) run python

# Backend status
status: ensure-poetry
	@echo "=== Backend Status ==="
	@cd $(BACKEND) && $(POETRY) show -- tree 2>/dev/null || $(POETRY) show

# Run evaluation
eval:
	@echo "Running KG triple evaluation..."
	@cd $(BACKEND) && python3 -c "import sys; sys.path.insert(0, 'app/kg'); from src.eval.runner import run_eval; extractor = lambda text: []; result = run_eval(extractor=extractor, dataset_path='data/eval/kg_triples_sample.jsonl'); metrics = result['metrics']; print(f'Metrics: {metrics}')"

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
