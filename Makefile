# Root Makefile for Terrarium workspace
# Runs checks and tests across vivarium and treehouse

PACKAGES := vivarium treehouse

.PHONY: help install check test test-coverage ci clean

.DEFAULT_GOAL := help

help: ## Display this help message
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

install: ## Install dependencies for all packages
	@for pkg in $(PACKAGES); do \
		echo "Installing $$pkg..."; \
		$(MAKE) -C $$pkg install; \
	done

check: ## Run format and lint checks for all packages
	@for pkg in $(PACKAGES); do \
		echo "Checking $$pkg..."; \
		$(MAKE) -C $$pkg check || exit 1; \
	done

test: ## Run tests for all packages
	@for pkg in $(PACKAGES); do \
		echo "Testing $$pkg..."; \
		$(MAKE) -C $$pkg test || exit 1; \
	done

test-coverage: ## Run tests with coverage for all packages
	@for pkg in $(PACKAGES); do \
		echo "Testing $$pkg with coverage..."; \
		$(MAKE) -C $$pkg test-coverage || exit 1; \
	done

ci: check test ## Run full CI pipeline
