# Makefile for treehouse
# Development automation and common tasks

.PHONY: help install test test-coverage lint format typecheck clean visualizer

SRC := src/treehouse/
SRC_MODULES := treehouse

# Default target
.DEFAULT_GOAL := help

##@ General

help: ## Display this help message
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Development Setup

install: ## Install package and dependencies
	uv sync
	@echo "✅ Installation complete!"

##@ Code Quality

format: ## Format code with black
	@echo "🎨 Formatting Python code..."
	uv run black $(SRC)
	@echo "✅ Formatting complete!"

lint: ## Lint code with flake8
	@echo "🔍 Linting code..."
	uv run ruff check $(SRC)
	@echo "✅ Linting complete!"

check: format lint typecheck ## Run all code quality checks
	@echo "✅ All checks passed!"

##@ Testing

test: ## Run all tests
	@echo "🧪 Running tests..."
	uv run pytest tests/ -v
	@echo "✅ Tests complete!"

test-coverage: ## Run tests with coverage report
	@echo "🧪 Running tests with coverage..."
	uv run pytest tests/ $(foreach mod,$(SRC_MODULES),--cov=$(mod)) --cov-report=html --cov-report=term
	@echo "✅ Coverage report generated in htmlcov/"

test-watch: ## Run tests in watch mode (requires pytest-watch)
	uv run ptw tests/ -- -v

test-unit: ## Run only unit tests
	uv run pytest tests/test_*.py -v -m "not integration"

test-integration: ## Run only integration tests
	uv run pytest tests/ -v -m integration

test-fast: ## Run tests without slow tests
	uv run pytest tests/ -v -m "not slow"

##@ Cleaning

clean: ## Remove build artifacts and cache
	@echo "🧹 Cleaning up..."
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	@echo "✅ Cleanup complete!"

##@ Visualizer

visualizer: ## Start the web visualizer server (dev mode with reload)
	@echo "🌐 Starting Treehouse Visualizer at http://localhost:8000..."
	uv run uvicorn treehouse.visualizer.server:app --reload

visualizer-prod: ## Start the web visualizer server (production mode)
	uv run uvicorn treehouse.visualizer.server:app --host 0.0.0.0 --port 8000

##@ CI/CD

ci: check test ## Run CI pipeline locally
	@echo "✅ CI checks passed!"

pre-commit: ## Install pre-commit hooks
	@echo "🪝 Installing pre-commit hooks..."
	pip install pre-commit
	pre-commit install
	@echo "✅ Pre-commit hooks installed!"

# Color definitions for fancy output
COLOR_RESET   = \033[0m
COLOR_INFO    = \033[36m
COLOR_SUCCESS = \033[32m
COLOR_WARNING = \033[33m
COLOR_ERROR   = \033[31m

# Print colored output
define print_color
	@echo "$(1)$(2)$(COLOR_RESET)"
endef

.PHONY: welcome
welcome: ## Display welcome message
	@echo ""
	@echo "╔════════════════════════════════════════════════════════════╗"
	@echo "║                                                            ║"
	@echo "║          🌳 Treehouse Development Tools 🔍                  ║"
	@echo "║                                                            ║"
	@echo "╚════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "Run 'make help' to see all available commands"
	@echo ""
