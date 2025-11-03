# Step Guide Backend API

Backend service for comprehensive step-by-step guide generation and progress tracking.

## Features

- **Guide Generation**: AI-powered step-by-step guide creation using LLM APIs
- **Progress Tracking**: Real-time step completion and progress monitoring
- **Dual Completion**: Desktop monitoring OR manual checkbox confirmation
- **Session Management**: Multi-user session support with state persistence
- **API-First**: REST API with OpenAPI documentation

## Tech Stack

- **Runtime**: Python 3.11+
- **Framework**: FastAPI with async support
- **Database**: PostgreSQL + Redis for session caching
- **LLM Integration**: OpenAI + Anthropic (dual provider)
- **Testing**: pytest with testcontainers
- **Deployment**: Docker containerized

## Quick Start

### Prerequisites
- Python 3.11+
- Docker and Docker Compose
- PostgreSQL and Redis (via Docker)

### Installation

1. Install dependencies:
```bash
pip install -e .[dev]
```

2. Start services:
```bash
docker-compose up -d
```

3. Run migrations:
```bash
alembic upgrade head
```

4. Start development server:
```bash
uvicorn src.main:app --reload --port 8000
```

### Testing

```bash
# Run all tests
pytest

# Run specific test types
pytest -m unit
pytest -m integration
pytest -m contract

# Run with coverage
pytest --cov=src --cov-report=html
```

## API Documentation

When running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json

## Development

### Code Quality
- Linting: `ruff check src/`
- Formatting: `black src/`
- Type checking: `mypy src/`

### Pre-commit hooks
```bash
pre-commit install
pre-commit run --all-files
```

## Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost/stepguide
REDIS_URL=redis://localhost:6379

# LLM APIs
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key

# Auth
SECRET_KEY=your_secret_key
ACCESS_TOKEN_EXPIRE_MINUTES=30

# App
DEBUG=false
LOG_LEVEL=info
```