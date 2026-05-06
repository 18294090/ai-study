.PHONY: all install install-torch dev test lint format clean backup eval eval-sample migrate migration shell status help ensure-poetry

# Python backend
BACKEND=backend
POETRY_VENV=$(CURDIR)/.poetry-venv
POETRY=$(POETRY_VENV)/bin/poetry

# CUDA version (default: cu124 for CUDA 12.4)
# Override with: make install CUDA_VERSION=cu118
CUDA_VERSION ?= cu124
TORCH_VERSION ?= 2.5.1
TORCHVISION_VERSION ?= 0.20.1

# Pip mirrors (domestic for speed)
PIP_INDEX        = https://pypi.tuna.tsinghua.edu.cn/simple
PYTORCH_CUDA_INDEX_PRIMARY  = https://mirrors.aliyun.com/pytorch-wheels/$(CUDA_VERSION)
PYTORCH_CUDA_INDEX_FALLBACK = https://download.pytorch.org/whl/$(CUDA_VERSION)
PIP_EXTRA_INDEX  = $(PYTORCH_CUDA_INDEX_PRIMARY)

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

# Pre-download torch/torchvision CUDA wheels via pip (resumes on partial download,
# avoids Poetry's single-shot downloader which fails on 900MB wheels).
install-torch: ensure-poetry
	@echo "==> Step 1/2: downloading torch + torchvision wheels (CUDA=$(CUDA_VERSION))..."
	@VENV="$(BACKEND)/.venv"; \
	if [ ! -x "$$VENV/bin/python" ]; then \
		echo "Creating project venv at $$VENV..."; \
		python3 -m venv "$$VENV"; \
	fi; \
	PIP="$$VENV/bin/python -m pip"; \
	PYTHON="$$VENV/bin/python"; \
	echo "Venv pip: $$PIP"; \
	echo "Target torch=$(TORCH_VERSION), torchvision=$(TORCHVISION_VERSION)"; \
	for i in 1 2 3 4 5; do \
		echo "  pip install torch attempt $$i/5..."; \
		$$PIP install \
			--index-url $(PYTORCH_CUDA_INDEX_PRIMARY) \
			--extra-index-url $(PYTORCH_CUDA_INDEX_FALLBACK) \
			--extra-index-url $(PIP_INDEX) \
			--timeout 900 --retries 50 \
			"torch==$(TORCH_VERSION)" "torchvision==$(TORCHVISION_VERSION)" && break; \
		echo "  attempt $$i failed, retrying..."; \
		sleep 5; \
	done; \
	"$$PYTHON" -c "import torch, torchvision; \
assert torch.__version__.startswith('$(TORCH_VERSION)'), f'torch={torch.__version__}'; \
assert torchvision.__version__.startswith('$(TORCHVISION_VERSION)'), f'torchvision={torchvision.__version__}'" >/dev/null 2>&1 || { \
		echo "Torch installation verification failed."; \
		exit 1; \
	}

# Install all other dependencies via Poetry (torch already in venv, Poetry will skip it)
install: install-torch
	@echo "==> Step 2/2: installing remaining dependencies via Poetry..."
	@cd $(BACKEND) && \
	$(POETRY) config virtualenvs.in-project true && \
	$(POETRY) env use .venv/bin/python && \
	$(POETRY) config installer.max-workers 4 && \
	$(POETRY) config installer.parallel true && \
	PIP_INDEX_URL=$(PIP_INDEX) \
	PIP_DEFAULT_TIMEOUT=300 \
	$(POETRY) install --no-interaction --without gpu
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
