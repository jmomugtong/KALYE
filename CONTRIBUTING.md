# Contributing to KALYE

Thank you for your interest in contributing to KALYE. This document covers the development setup, coding standards, and pull request process.

## Development Setup

### Prerequisites

- Python 3.11+
- Node.js 20+ and npm
- Docker and Docker Compose
- Poetry (Python dependency management)

### Getting Started

```bash
# Clone the repository
git clone https://github.com/your-org/kalye.git
cd kalye

# Copy environment config
cp .env.example .env

# Install backend dependencies
cd backend && poetry install && cd ..

# Install frontend dependencies
cd frontend && npm install && cd ..

# Start infrastructure (PostgreSQL, Redis, MinIO)
make dev-infra

# Run database migrations
make migrate

# Seed the database with sample data
python backend/scripts/seed_database.py

# Start the development servers
make dev
```

### Running Services Individually

```bash
# Backend API only
cd backend && poetry run uvicorn api.main:app --reload

# Frontend only
cd frontend && npm run dev

# Celery workers
cd backend && poetry run celery -A workers.celery_app worker --loglevel=info
```

## Code Style

### Python (Backend)

- **Formatter**: [Black](https://github.com/psf/black) (line length: 100)
- **Import sorting**: [isort](https://pycqa.github.io/isort/) (profile: black)
- **Linter**: [flake8](https://flake8.pycqa.org/) with flake8-bugbear
- **Type checking**: [mypy](https://mypy-lang.org/) (strict mode)

```bash
# Format
black backend/ && isort backend/

# Lint
flake8 backend/
mypy backend/
```

### TypeScript (Frontend)

- **Linter**: [ESLint](https://eslint.org/) with Next.js recommended rules
- **Formatter**: [Prettier](https://prettier.io/)

```bash
cd frontend
npm run lint
npm run format
```

### General Rules

- No `print()` in production code; use `logging` or `structlog`.
- All public functions and classes must have docstrings.
- Keep functions under 50 lines where practical.
- Prefer explicit over implicit; avoid magic numbers.

## Testing

### Backend

```bash
# Run all backend tests
cd backend && poetry run pytest

# With coverage
poetry run pytest --cov=src --cov-report=term-missing

# Run a specific test file
poetry run pytest tests/test_db.py -v
```

### Frontend

```bash
cd frontend
npm test              # Run Jest tests
npm run test:coverage # With coverage report
```

### Coverage Requirements

- **Minimum coverage**: 80% for both backend and frontend.
- New features must include tests. Bug fixes should include a regression test.
- AI model evaluation thresholds are documented in `CLAUDE.md`.

## Pull Request Process

### Branch Naming

Use the following prefixes:

| Prefix | Purpose |
|--------|---------|
| `feat/` | New feature |
| `fix/` | Bug fix |
| `refactor/` | Code restructuring (no behavior change) |
| `docs/` | Documentation only |
| `test/` | Adding or updating tests |
| `chore/` | Build config, dependencies, CI |

Example: `feat/walkability-score-api`, `fix/detection-confidence-threshold`

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `perf`, `ci`

Examples:

```
feat(api): add walkability score endpoint
fix(worker): correct confidence threshold comparison
docs(readme): update architecture diagram
test(db): add integration tests for Location model
```

### Review Checklist

Before requesting a review, verify:

- [ ] Code follows the style guidelines above.
- [ ] All existing tests pass (`make test`).
- [ ] New code has corresponding tests.
- [ ] Coverage has not decreased below 80%.
- [ ] No secrets, credentials, or API keys are committed.
- [ ] Database migrations are included if models changed.
- [ ] Documentation is updated if behavior changed.
- [ ] PR description explains *what* and *why*.

### Review Expectations

- At least one approving review is required before merge.
- Address all review comments or explain why they are not applicable.
- Squash commits before merge if the history is noisy.

## Reporting Issues

When filing a bug report, include:

1. **Summary**: One-sentence description of the problem.
2. **Environment**: OS, Python/Node version, Docker version.
3. **Steps to reproduce**: Minimal sequence to trigger the bug.
4. **Expected behavior**: What should happen.
5. **Actual behavior**: What actually happens (include error messages/logs).
6. **Screenshots**: If the issue is visual (map rendering, UI layout).

For feature requests, describe the use case and the expected outcome. Reference specific barangays or infrastructure issues if applicable.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
