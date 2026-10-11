.PHONY: help setup data bank simulate models pilot verify analysis report all smoke test test-ui lint format web serve screenshots clean

help: ## List targets
	@grep -E '^[a-z0-9-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

setup: ## Install Python (uv) and web (npm) dependencies
	uv sync --locked
	npm --prefix web ci

data: ## Download the three UCI datasets and check their SHA-256
	uv run declab data

bank: data ## Fit and calibrate the AI per domain and draw the case bank (data/bank/, committed)
	uv run declab bank

simulate: ## Simulated dry runs through the API: planted effects and no effect
	uv run declab simulate planted
	uv run declab simulate no_effect

models: ## Download the two local open-weights models (about 5 GB) and check their SHA-256
	uv sync --locked --extra llm
	uv run declab models

pilot: ## Model-participant pilot through the API (resumable; hours on CPU)
	uv run declab pilot

verify: ## Check the hash chain of every committed session log
	uv run declab verify

analysis: verify ## Pre-registered analysis into results/<UTC>-<sha7>, then the generated report
	uv run declab analyse
	uv run declab report

all: bank simulate analysis ## Rebuild the bank, rerun the dry runs, analyse every log (the model pilot is `make models pilot`)

smoke: verify ## Quick analysis of the committed logs into results/scratch (checks the pipeline, not a result)
	rm -rf results/scratch
	uv run declab analyse --quick --results results/scratch

test: ## Unit, API, store, design and analysis tests (offline; no models)
	uv run pytest

test-ui: web ## Browser tests: participant flow, console, keyboard, axe in both themes
	uv run pytest -m ui

lint: ## Ruff, mypy strict, ESLint and TypeScript
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy src tests scripts
	npm --prefix web run lint
	npm --prefix web run typecheck

format: ## Auto-format Python
	uv run ruff format .
	uv run ruff check --fix .

web: ## Build the interface into web/dist
	npm --prefix web run build

serve: web ## Serve the study and the console on http://127.0.0.1:8015 (study at /study)
	uv run declab serve

screenshots: web ## Capture docs/screenshots from the committed result
	uv run python scripts/screenshots.py

clean: ## Remove build output and scratch runs (keeps data/ and results/)
	rm -rf web/dist results/scratch var .pytest_cache .mypy_cache .ruff_cache
