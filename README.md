# KALYE — Knowledge-driven Analytics for Local Yield and Environments

AI-powered walkability intelligence for Metro Manila. Analyzes street imagery using computer vision to detect infrastructure issues and score pedestrian safety across barangays.

## Architecture

```
┌──────────────────────┐     ┌──────────────────────────────────┐
│  Next.js 14 Frontend │────▶│  FastAPI + Strawberry GraphQL    │
│  Mapbox GL + React   │     │  OAuth2/JWT + Rate Limiting      │
└──────────────────────┘     └──────┬──────────────┬────────────┘
                                    │              │
                                    ▼              ▼
                             ┌────────────┐  ┌─────────────────┐
                             │ Core       │  │ Celery Workers   │
                             │ Services   │  │ (Redis Queue)    │
                             │            │  │                  │
                             │ • Geo      │  │ • YOLOv8 detect  │
                             │ • Reports  │  │ • SegFormer seg  │
                             │ • Scoring  │  │ • BLIP-2 caption │
                             └─────┬──────┘  └────────┬─────────┘
                                   │                  │
                                   ▼                  ▼
                    ┌─────────────────────────────────────────┐
                    │  PostgreSQL+PostGIS │ Redis │ MinIO (S3) │
                    └─────────────────────────────────────────┘
```

## Quick Start

### Prerequisites
- Python 3.11+, Poetry
- Node.js 20+, npm
- Docker & Docker Compose

### Setup

```bash
# Clone and configure
cp .env.example .env

# Install dependencies
make install

# Start infrastructure (Postgres, Redis, MinIO)
make dev-infra

# Run database migrations
make migrate

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
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, TypeScript, Tailwind, Mapbox GL, TanStack Query |
| API | FastAPI, Strawberry GraphQL, OAuth2/JWT |
| Workers | Celery, Redis |
| AI Models | YOLOv8, SegFormer, BLIP-2 (all open-source, local inference) |
| Database | PostgreSQL 15 + PostGIS 3.3 |
| Storage | MinIO (S3-compatible) |
| Observability | OpenTelemetry, Prometheus, Grafana |
| CI/CD | GitHub Actions, Docker |

## License

MIT
