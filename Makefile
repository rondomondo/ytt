.DEFAULT_GOAL := help
.PHONY: help install lint format typecheck check

UV := uv
SCRIPT := ytt.py

help: ## Show available targets
	@grep -E '^[a-z]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

install: ## Sync dev dependencies and enable git hooks
	$(UV) sync --extra dev
	git config core.hooksPath .githooks
	chmod +x .githooks/commit-msg $(SCRIPT)

lint: ## Run ruff lint
	$(UV) run ruff check .

format: ## Check ruff formatting
	$(UV) run ruff format --check .

typecheck: ## Run mypy
	$(UV) run mypy .

check: lint format typecheck ## Run all checks
