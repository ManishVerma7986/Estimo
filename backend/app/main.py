"""FastAPI Application Entry Point."""

from __future__ import annotations
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.datasets import router as datasets_router
from backend.app.api.estimates import router as estimates_router
from backend.app.api.health import router as health_router
from backend.app.api.models import router as models_router
from backend.app.api.reports import router as reports_router
from backend.app.api.scenarios import router as scenarios_router
from backend.app.api.schemas import router as schemas_router
from backend.app.api.training import router as training_router
from backend.app.core.config import settings
from ml.registry import ModelRegistry


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup validation: verify offline model availability
    reg = ModelRegistry(base_dir=settings.base_dir)
    active = reg.load_registry().get("active_models", {})
    print(f"[{settings.app_name}] Started offline-capable service. Active models on disk: {list(active.keys())}")
    yield
    print(f"[{settings.app_name}] Shutting down.")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Production-quality offline-capable cost estimation engine for product development.",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(health_router, prefix=settings.api_prefix)
app.include_router(datasets_router, prefix=settings.api_prefix)
app.include_router(schemas_router, prefix=settings.api_prefix)
app.include_router(training_router, prefix=settings.api_prefix)
app.include_router(models_router, prefix=settings.api_prefix)
app.include_router(estimates_router, prefix=settings.api_prefix)
app.include_router(scenarios_router, prefix=settings.api_prefix)
app.include_router(reports_router, prefix=settings.api_prefix)


@app.get("/")
def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "status": "online_offline_capable",
        "docs_url": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=True)
