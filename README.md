# Digital Twin Supply Chain Platform

A production-grade Digital Twin for supply chain operations. Integrates with any ERP or TMS via a generic adapter pattern, provides real-time simulation, KPI analytics, and writeback capabilities.

## Quick Start

```bash
# 1. Copy env file
cp .env.example .env

# 2. Start the full stack
cd infra && docker-compose up

# 3. Run database migrations (new terminal)
cd backend && alembic upgrade head

# 4. Seed development data
cd backend && python -c "import asyncio; from app.db.seed import seed_dev_data; asyncio.run(seed_dev_data())"

# 5. Simulate live ERP feed
python scripts/simulate_kafka_feed.py
```

## Services
| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| Kafka UI | http://localhost:8080 |

## Development

```bash
# Backend tests
cd backend && pytest tests/ -v

# Frontend tests
cd frontend && npm test

# Lint
cd backend && ruff check app/ && black --check app/
cd frontend && npm run lint
```

## Architecture
See `docs/architecture.md` for full system design.
