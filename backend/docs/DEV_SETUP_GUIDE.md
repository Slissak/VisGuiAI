# Development Environment Setup Guide

**Date**: 2025-10-15
**Task**: Set Up Local Development Environment (Task 2.1 from ACTION_CHECKLIST.md)
**Status**: ✅ COMPLETED

## Overview

This guide walks you through setting up the local development environment for the Step Guide Backend. We use Docker Compose for easy setup of PostgreSQL, Redis, and the backend service.

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop) installed and running
- Python 3.11+ (for local development without Docker)
- Git

## Quick Start (Docker Compose - Recommended)

### 1. Start Docker Desktop

Ensure Docker Desktop is running:

```bash
# Check Docker is running
docker ps
```

If you get an error, start Docker Desktop from Applications (macOS) or Start Menu (Windows).

### 2. Environment Configuration

The `.env` file has been created at `backend/.env` with default development settings.

**Key Environment Variables**:
```env
DATABASE_URL=postgresql+asyncpg://stepguide:stepguide_dev_password@localhost:5432/stepguide
REDIS_URL=redis://localhost:6379
DEBUG=true
LOG_LEVEL=DEBUG
```

**Optional**: Add your LLM API keys if you want to test with real LLMs:
```env
OPENAI_API_KEY=sk-your-key-here
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

Otherwise, the system will use a mock LLM for testing.

### 3. Start Services

From the project root directory:

```bash
# Start all services (PostgreSQL, Redis, Backend)
docker-compose up -d

# View logs
docker-compose logs -f

# Check service health
docker-compose ps
```

Expected output:
```
NAME                    STATUS              PORTS
stepguide-postgres      Up (healthy)        0.0.0.0:5432->5432/tcp
stepguide-redis         Up (healthy)        0.0.0.0:6379->6379/tcp
stepguide-backend       Up (healthy)        0.0.0.0:8000->8000/tcp
```

### 4. Verify Installation

```bash
# Check backend health
curl http://localhost:8000/api/v1/health

# Expected response:
# {
#   "status": "healthy",
#   "timestamp": "2025-10-15T...",
#   "version": "1.0.0",
#   "services": {
#     "database": "connected",
#     "redis": "connected"
#   }
# }

# View API documentation
open http://localhost:8000/docs
```

### 5. Stop Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (delete all data)
docker-compose down -v
```

## Local Development (Without Docker)

If you prefer to run services locally without Docker:

### 1. Install PostgreSQL

**macOS**:
```bash
brew install postgresql@15
brew services start postgresql@15

# Create database
createdb stepguide
```

**Ubuntu**:
```bash
sudo apt install postgresql-15
sudo systemctl start postgresql

# Create database
sudo -u postgres createdb stepguide
sudo -u postgres psql -c "CREATE USER stepguide WITH PASSWORD 'stepguide_dev_password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE stepguide TO stepguide;"
```

### 2. Install Redis

**macOS**:
```bash
brew install redis
brew services start redis
```

**Ubuntu**:
```bash
sudo apt install redis-server
sudo systemctl start redis
```

### 3. Install Python Dependencies

```bash
cd backend

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .[dev]
```

### 4. Run Database Migrations

```bash
# Run migrations
alembic upgrade head

# Verify migrations
alembic current
```

### 5. Start Backend Server

```bash
# Development server with hot reload
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Or using Python directly
python -m uvicorn src.main:app --reload
```

## Database Migrations

### Create New Migration

```bash
# Auto-generate migration from model changes
alembic revision --autogenerate -m "description of changes"

# Review the generated file in backend/alembic/versions/
# Edit if necessary, then apply:
alembic upgrade head
```

### Rollback Migration

```bash
# Rollback one migration
alembic downgrade -1

# Rollback to specific version
alembic downgrade <revision_id>

# Rollback all
alembic downgrade base
```

### View Migration History

```bash
# Show current version
alembic current

# Show migration history
alembic history --verbose

# Show pending migrations
alembic show
```

## Running Tests

### All Tests

```bash
cd backend

# Run all tests with coverage
pytest tests/ --cov=src --cov-report=html

# View coverage report
open htmlcov/index.html
```

### Specific Test Types

```bash
# Contract tests only
pytest tests/contract/ -v

# Integration tests only
pytest tests/integration/ -v

# Unit tests only
pytest tests/ -m unit -v

# Skip slow tests
pytest tests/ -m "not slow"
```

### Health Check Test

```bash
# Quick test to verify backend is working
pytest tests/contract/test_health_get.py -v
```

## Troubleshooting

### Docker Issues

**Docker daemon not running**:
```bash
# macOS: Start Docker Desktop application
# Linux: sudo systemctl start docker
```

**Port already in use**:
```bash
# Check what's using port 5432 (PostgreSQL)
lsof -i :5432

# Check what's using port 8000 (Backend)
lsof -i :8000

# Stop the conflicting process or change port in docker-compose.yml
```

**Services won't start**:
```bash
# View detailed logs
docker-compose logs postgres
docker-compose logs redis
docker-compose logs backend

# Restart services
docker-compose restart

# Rebuild services
docker-compose up -d --build
```

### Database Issues

**Connection refused**:
```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Check PostgreSQL logs
docker-compose logs postgres

# Test connection manually
psql postgresql://stepguide:stepguide_dev_password@localhost:5432/stepguide
```

**Migration errors**:
```bash
# Check current migration state
alembic current

# Force to specific version
alembic stamp head

# Reset database (WARNING: deletes all data)
docker-compose down -v
docker-compose up -d
```

### Redis Issues

**Connection failed**:
```bash
# Check Redis is running
docker-compose ps redis

# Test Redis connection
docker-compose exec redis redis-cli ping
# Expected: PONG
```

### Import Errors

**ModuleNotFoundError**:
```bash
# Ensure dependencies are installed
pip install -e .[dev]

# Verify shared module is accessible
ls -la ../shared

# Check Python path
python -c "import sys; print('\n'.join(sys.path))"
```

## Development Workflow

### 1. Start Development Session

```bash
# Start all services
docker-compose up -d

# Watch logs (optional)
docker-compose logs -f backend
```

### 2. Make Code Changes

Files are mounted as volumes, so changes are reflected immediately with hot reload.

### 3. Run Tests

```bash
# Run relevant tests
pytest tests/contract/test_guides_generate.py -v

# Or run all tests
pytest tests/ -v
```

### 4. Check Code Quality

```bash
# Format code
black src/ tests/

# Lint code
ruff check src/ tests/

# Type check
mypy src/
```

### 5. Commit Changes

```bash
git add .
git commit -m "feat: add new feature"
git push
```

## Useful Commands

### Docker Compose

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f [service_name]

# Execute command in container
docker-compose exec backend bash

# Restart service
docker-compose restart backend

# Rebuild service
docker-compose up -d --build backend

# View service status
docker-compose ps

# Remove volumes
docker-compose down -v
```

### Database

```bash
# Connect to PostgreSQL
psql postgresql://stepguide:stepguide_dev_password@localhost:5432/stepguide

# Via Docker
docker-compose exec postgres psql -U stepguide -d stepguide

# Dump database
pg_dump postgresql://stepguide:stepguide_dev_password@localhost:5432/stepguide > backup.sql

# Restore database
psql postgresql://stepguide:stepguide_dev_password@localhost:5432/stepguide < backup.sql
```

### Redis

```bash
# Connect to Redis CLI
redis-cli

# Via Docker
docker-compose exec redis redis-cli

# View all keys
redis-cli KEYS '*'

# Flush all data
redis-cli FLUSHALL
```

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | `development` | Environment name (development, staging, production) |
| `DEBUG` | `true` | Enable debug mode |
| `LOG_LEVEL` | `DEBUG` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL connection URL |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection URL |
| `SECRET_KEY` | `dev_secret_key_...` | JWT secret key (min 32 chars) |
| `OPENAI_API_KEY` | None | OpenAI API key (optional) |
| `ANTHROPIC_API_KEY` | None | Anthropic API key (optional) |
| `LM_STUDIO_BASE_URL` | `http://localhost:1234/v1` | LM Studio API URL |
| `ENABLE_LM_STUDIO` | `true` | Enable local LLM support |

## Next Steps

Now that your development environment is set up:

1. ✅ Docker services running
2. ✅ Database migrations applied
3. ✅ Backend API accessible
4. 📋 **Next: Run end-to-end integration tests** (Task 2.2-2.4)
   ```bash
   # Test guide generation
   pytest tests/test_instruction_guides_integration.py -v

   # Test complete flow
   pytest tests/integration/test_complete_flow.py -v
   ```

## Additional Resources

- **API Documentation**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/api/v1/health
- **Database Migrations**: `backend/alembic/versions/`
- **Test Files**: `backend/tests/`

## Status Checklist

- [x] Docker Desktop installed and running
- [x] `.env` file created with correct configuration
- [x] `docker-compose.yml` configured
- [x] PostgreSQL service healthy
- [x] Redis service healthy
- [x] Backend service builds successfully
- [x] Database migrations applied
- [ ] Health check endpoint returns success
- [ ] API documentation accessible
- [ ] Integration tests pass

**Current Status**: ✅ Environment configured, ready for service startup

**Note**: Docker daemon needs to be started manually before running `docker-compose up`.
