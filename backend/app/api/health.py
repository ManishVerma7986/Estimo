"""Health and System Status API."""

from __future__ import annotations
from fastapi import APIRouter
from backend.app.schemas.model import ModelHealthReport
from ml.registry import ModelRegistry

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=ModelHealthReport)
def get_health_status() -> ModelHealthReport:
    """Returns application status, active models, offline-capability flag, and checksum verification."""
    registry = ModelRegistry()
    reg_data = registry.load_registry()
    active_models = reg_data.get("active_models", {})
    checksums = registry.verify_all_models()

    return ModelHealthReport(
        status="ok",
        models_available=len(active_models) > 0,
        active_models_count=len(active_models),
        active_models=active_models,
        checksum_verification=checksums,
        offline_capable=True
    )
