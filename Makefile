.PHONY: install dev test test-cov eval load-test docker-up docker-down docker-build format lint type-check seed migrate download-models

# ─── Setup ────────────────────────────────────────────────────────────────────

install:
	cd backend && poetry install
	cd frontend && npm install

download-models:
	cd backend && poetry run python -m src.ai.model_manager download

# ─── Development ──────────────────────────────────────────────────────────────

dev:
	docker compose up -d postgres redis minio
	@echo "Waiting for services to start..."
	sleep 3
	cd backend && poetry run uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000 &
	cd backend && poetry run celery -A src.workers.celery_app worker --loglevel=info --concurrency=4 &
	cd frontend && npm run dev

dev-infra:
	docker compose up -d postgres redis minio prometheus grafana

stop:
	docker compose down
	-pkill -f "uvicorn src.api.main:app" 2>/dev/null || true
	-pkill -f "celery -A src.workers" 2>/dev/null || true

# ─── Database ─────────────────────────────────────────────────────────────────

migrate:
	cd backend && poetry run alembic upgrade head

migrate-create:
	cd backend && poetry run alembic revision --autogenerate -m "$(msg)"

seed:
	cd backend && poetry run python -m src.db.seed
	python data/scripts/download_osm.py --bbox=14.4,120.9,14.8,121.1

# ─── Testing ──────────────────────────────────────────────────────────────────

test:
	cd backend && poetry run pytest tests/ -v
	cd frontend && npm run test

test-cov:
	cd backend && poetry run pytest tests/ -v --cov=src --cov-report=html --cov-report=term
	cd frontend && npm run test -- --coverage

test-unit:
	cd backend && poetry run pytest tests/unit/ -v

test-integration:
	cd backend && poetry run pytest tests/integration/ -v

# ─── AI Model Evaluation ─────────────────────────────────────────────────────

eval:
	python scripts/eval_detection.py --model models/yolov8_pothole.pt --data data/evals/metro_manila_labeled --threshold 0.75
	python scripts/eval_segmentation.py --model models/segformer_sidewalk.pt --iou-threshold 0.65
	python scripts/eval_bias.py --output reports/bias_analysis.json

load-test:
	k6 run backend/tests/load/k6_upload.js

# ─── Code Quality ─────────────────────────────────────────────────────────────

format:
	cd backend && poetry run ruff format src/ tests/
	cd frontend && npx prettier --write "**/*.{ts,tsx,js,json,css}"

lint:
	cd backend && poetry run ruff check src/ tests/
	cd frontend && npm run lint

type-check:
	cd backend && poetry run mypy src/
	cd frontend && npm run type-check

# ─── Docker ───────────────────────────────────────────────────────────────────

docker-up:
	docker compose up --build

docker-down:
	docker compose down -v

docker-build:
	docker build -t kalye-api -f infrastructure/docker/Dockerfile.api ./backend
	docker build -t kalye-worker -f infrastructure/docker/Dockerfile.worker ./backend
	docker build -t kalye-frontend -f infrastructure/docker/Dockerfile.frontend ./frontend

# ─── Deployment ───────────────────────────────────────────────────────────────

deploy:
	$(MAKE) docker-build
	@echo "Push images to your container registry and deploy."
