import asyncio
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.session import engine

logger = structlog.get_logger()


async def _start_ingest_processors() -> list[asyncio.Task]:
    """Start all Kafka consumer processors as background asyncio tasks."""
    from app.ingest.processors.inventory_processor import InventoryProcessor
    from app.ingest.processors.order_processor import OrderProcessor
    from app.ingest.processors.shipment_processor import ShipmentProcessor

    processors = [OrderProcessor(), ShipmentProcessor(), InventoryProcessor()]
    tasks = [asyncio.create_task(p.consume_loop(), name=type(p).__name__) for p in processors]
    logger.info("ingest.processors_started", count=len(tasks))
    return tasks


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup", environment=settings.environment)
    processor_tasks = await _start_ingest_processors()
    yield
    for task in processor_tasks:
        task.cancel()
    await asyncio.gather(*processor_tasks, return_exceptions=True)
    await engine.dispose()
    logger.info("shutdown")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["System"])
async def health():
    return {"status": "ok", "environment": settings.environment}


@app.get("/health/ingest", tags=["System"])
async def health_ingest():
    """Reports running state of each Kafka processor task."""
    tasks = {t.get_name(): not t.done() for t in asyncio.all_tasks() if t.get_name() in
             ("OrderProcessor", "ShipmentProcessor", "InventoryProcessor")}
    all_healthy = all(tasks.values())
    return {"status": "ok" if all_healthy else "degraded", "processors": tasks}
