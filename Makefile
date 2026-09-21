# Dreamwalker. `make` on its own runs everything CI runs.
#
# Everything here is offline and free. The one target that can spend money is
# `eval-live`, and it says so.

.DEFAULT_GOAL := check
.PHONY: check test cover lint format eval eval-live eval-json web api docs clean

BACKEND := cd backend && uv run

check: lint test eval web api ## everything CI runs

test: ## backend unit tests
	$(BACKEND) pytest -q

cover: ## the same, with a per-file coverage report
	$(BACKEND) pytest -q --cov=app --cov-report=term-missing

lint: ## ruff, both halves
	$(BACKEND) ruff check .
	$(BACKEND) ruff format --check .

format: ## fix what `lint` complains about
	$(BACKEND) ruff check --fix .
	$(BACKEND) ruff format .

eval: ## the offline eval suite: pass rates per dimension
	cd backend && PYTHONPATH=. uv run python -m evals

eval-json: ## the same, for something that is not a person
	cd backend && PYTHONPATH=. uv run python -m evals --json

eval-live: ## re-run the dimensions a real model can be judged on. SPENDS MONEY.
	cd backend && PYTHONPATH=. uv run python -m evals --live --verbose

web: ## typecheck and build the frontend
	bun run build

api: ## the frontend's types must still match the backend's schema
	bun run gen:api:ci
	git diff --exit-code web/src/api/schema.d.ts

docs: ## regenerate the style catalog page from the code
	$(BACKEND) python -m app.pipeline.style_catalog > ../docs/style-cards.md

clean:
	rm -rf backend/.pytest_cache backend/.ruff_cache backend/.coverage web/dist
	find backend -name __pycache__ -type d -prune -exec rm -rf {} +
