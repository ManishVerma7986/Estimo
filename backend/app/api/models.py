"""Model Registry and Version Management API."""

from __future__ import annotations
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException

from backend.app.schemas.model import ActivateModelRequest, ModelItem, RollbackModelRequest
from ml.registry import ModelRegistry

router = APIRouter(prefix="/models", tags=["Models"])
registry = ModelRegistry()


@router.get("", response_model=List[ModelItem])
def list_models() -> List[ModelItem]:
    """Lists all stored models with metrics and checksum validation status."""
    raw_list = registry.list_models()
    return [
        ModelItem(
            model_key=m["model_key"],
            target=m["target"],
            version=m["version"],
            algorithm=m["algorithm"],
            dataset_id=m["dataset_id"],
            status=m["status"],
            is_active=m["is_active"],
            sha256=m["sha256"],
            metrics=m.get("metrics", {}),
            registered_at=m.get("registered_at", "")
        )
        for m in raw_list
    ]


@router.post("/activate", response_model=Dict[str, str])
def activate_model_version(req: ActivateModelRequest) -> Dict[str, str]:
    try:
        registry.activate_model(req.target, req.version)
        return {"message": f"Activated version '{req.version}' for target '{req.target}'."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/rollback", response_model=Dict[str, Any])
def rollback_model_version(req: RollbackModelRequest) -> Dict[str, Any]:
    prev = registry.rollback_model(req.target)
    if prev:
        return {"message": f"Rolled back target '{req.target}' to version '{prev}'.", "active_version": prev}
    raise HTTPException(status_code=400, detail=f"No previous version found for target '{req.target}'.")


@router.get("/verify", response_model=Dict[str, bool])
def verify_model_checksums() -> Dict[str, bool]:
    """Cryptographic integrity check of all model joblib files on disk."""
    return registry.verify_all_models()
