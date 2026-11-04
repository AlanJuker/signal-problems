.PHONY: up down ingest ingest-history ingest-surface model check check-backend check-frontend api-types

up: ## Start PostgreSQL, the API and the web app on http://localhost:8080
	docker compose up --build -d

down:
	docker compose down

ingest: ## Download the TTC delay log and load it into the database
	docker compose exec api signal-problems ingest

ingest-history: ## Also load 2014–2024 (about 268,000 rows)
	docker compose exec api signal-problems ingest --history

ingest-surface: ## Also load streetcar and bus delays since 2025, by route
	docker compose exec api signal-problems ingest --mode streetcar
	docker compose exec api signal-problems ingest --mode bus

model: ## Train the delay model and store next week's forecasts (rebuilds the API with ML=true)
	ML=true docker compose up --build --detach --wait api
	docker compose exec api signal-problems train-model

check: check-backend check-frontend ## Everything CI runs

check-backend:
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest

check-frontend:
	cd frontend && npm run typecheck && npm run lint && npm test && npm run build

api-types: ## Regenerate the frontend's API types after changing the API
	cd frontend && npm run api:types
