# KALYE — Knowledge-driven Analytics for Local Yield and Environments

AI-powered walkability intelligence for Metro Manila. Analyzes street imagery using computer vision to detect infrastructure issues and score pedestrian safety across barangays.

## Features

- **Street-level infrastructure detection** — Identifies potholes, sidewalk obstructions, missing signs, broken curbs, and flooding using YOLOv8 object detection.
- **Semantic segmentation** — Maps sidewalks, roads, and curb boundaries with SegFormer for precise coverage measurement.
- **Automated image captioning** — Generates human-readable descriptions of street conditions using BLIP-2.
- **Walkability scoring** — Composite scores per barangay based on sidewalk coverage, obstruction density, ADA compliance, and temporal decay.
- **Interactive map dashboard** — Mapbox GL-powered visualization with heatmaps, cluster markers, and barangay-level drill-down.
- **Privacy-first** — Automatic face and license plate blurring on all uploaded street imagery.
- **RAG-powered chat** — Ask natural language questions about walkability data using local LLM with vector search.
- **Open-source AI** — All inference runs locally with free Hugging Face models; no paid API dependencies.

## Architecture

```
                           ┌────────────────────────┐
                           │     Next.js 14 App      │
                           │  Mapbox GL + TanStack    │
                           │  Tailwind + shadcn/ui    │
                           └───────────┬────────────┘
                                       │ REST / GraphQL
                                       ▼
                      ┌─────────────────────────────────┐
                      │   FastAPI + Strawberry GraphQL   │
                      │   OAuth2/JWT │ Redis Rate Limit  │
                      └──────┬──────────────┬───────────┘
                             │              │
                  ┌──────────▼──────┐ ┌─────▼──────────────┐
                  │  Core Services  │ │   Celery Workers    │
                  │                 │ │   (Redis Queue)     │
                  │  • Geo/PostGIS  │ │                     │
                  │  • Scoring      │ │  • YOLOv8 detect    │
                  │  • Reports      │ │  • SegFormer seg    │
                  │  • RAG Chat     │ │  • BLIP-2 caption   │
                  └────────┬────────┘ └──────────┬─────────┘
                           │                     │
                           ▼                     ▼
         ┌──────────────────────────────────────────────────┐
         │  PostgreSQL 15 + PostGIS │ Redis │ MinIO (S3)    │
         │         pgvector         │ cache │ image store   │
         └──────────────────────────────────────────────────┘
                           │
                           ▼
         ┌──────────────────────────────────────────────────┐
         │  OpenTelemetry  →  Prometheus  →  Grafana        │
         └──────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+, Poetry
- Node.js 20+, npm
- Docker & Docker Compose

### Docker Compose (Recommended)

```bash
# Clone and configure
git clone https://github.com/your-org/kalye.git
cd kalye
cp .env.example .env

# Start the full stack
make docker-up

# Seed the database
python backend/scripts/seed_database.py

# Open the app
# Frontend:    http://localhost:3000
# API Docs:    http://localhost:8000/docs
# Grafana:     http://localhost:3001
```

### Development Setup

```bash
# Install dependencies
make install

# Start infrastructure (Postgres, Redis, MinIO)
make dev-infra

# Run database migrations
make migrate

# Download AI models
python backend/scripts/download_models.py --model all

# Seed sample data
python backend/scripts/seed_database.py

# Start all services
make dev
```

### Key URLs

- **Frontend**: http://localhost:3000
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **MinIO Console**: http://localhost:9001
- **Grafana**: http://localhost:3001
- **Prometheus**: http://localhost:9090

## Development

```bash
make test          # Run all tests
make test-unit     # Backend unit tests only
make lint          # Lint backend + frontend
make format        # Auto-format code
make eval          # Run AI model evaluations
make docker-up     # Full stack via Docker Compose
make docker-down   # Tear down Docker stack
```

### Utility Scripts

| Script | Description |
|--------|-------------|
| `backend/scripts/download_models.py` | Download AI model artifacts from Hugging Face |
| `backend/scripts/seed_database.py` | Seed barangays, users, and walkability scores |
| `backend/scripts/health_check.py` | Check PostgreSQL, Redis, MinIO, Ollama status |
| `backend/scripts/performance_benchmark.py` | Benchmark inference, DB, and storage latency |
| `backend/scripts/backup_database.py` | pg_dump backup with gzip and retention policy |
| `scripts/generate_launch_checklist.py` | Deployment readiness checks and scoring |

## Testing

### Backend

```bash
cd backend
poetry run pytest                                    # All tests
poetry run pytest --cov=src --cov-report=term-missing # With coverage
poetry run pytest tests/test_db.py -v                # Specific file
```

### Frontend

```bash
cd frontend
npm test              # Jest tests
npm run test:coverage # With coverage
```

### AI Model Evaluation

| Task | Metric | Threshold |
|------|--------|-----------|
| Pothole Detection | mAP@0.5 | >0.75 |
| Sidewalk Segmentation | IoU | >0.65 |
| Obstruction Detection | Precision | >0.80 |
| District Bias Variance | Std Dev | <0.10 |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, TypeScript, Tailwind, Mapbox GL, TanStack Query |
| API | FastAPI, Strawberry GraphQL, OAuth2/JWT |
| Workers | Celery, Redis |
| AI Models | YOLOv8, SegFormer, BLIP-2 (all open-source, local inference) |
| Database | PostgreSQL 15 + PostGIS 3.3 + pgvector |
| Storage | MinIO (S3-compatible) |
| Observability | OpenTelemetry, Prometheus, Grafana |
| CI/CD | GitHub Actions, Docker |

## Known Limitations

- **Pre-implementation stage**: Core AI pipeline and API endpoints are under active development. See `docs/` for the phased build plan.
- **Metro Manila only**: Barangay boundaries and walkability scoring are currently scoped to Metro Manila. Expanding to other regions requires new GeoJSON datasets.
- **GPU recommended**: While CPU inference is supported, YOLOv8 and SegFormer perform significantly better with CUDA-enabled GPUs.
- **BLIP-2 memory**: The BLIP-2 OPT 2.7B model requires approximately 6 GB of VRAM. Consider using a smaller variant for resource-constrained environments.
- **No mobile app**: The platform is web-only. A progressive web app (PWA) wrapper is planned for Phase 5.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines, code style, and the PR process.

## License

MIT
