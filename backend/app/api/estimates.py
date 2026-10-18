"""Estimates and Actuals Tracking API."""

from __future__ import annotations
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException

from backend.app.core.config import settings
from backend.app.schemas.estimate import ActualOutcomeRecord, CreateEstimateRequest
from backend.app.services.estimation import generate_full_estimate, UnifiedEstimateResult

router = APIRouter(prefix="/estimates", tags=["Estimates"])

HISTORY_FILE = settings.base_dir / "reports" / "estimate_history.json"
ACTUALS_FILE = settings.base_dir / "reports" / "actual_outcomes.json"


def _load_json_list(path: Path) -> List[Dict[str, Any]]:
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def _save_json_list(path: Path, data: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


@router.post("", response_model=UnifiedEstimateResult)
def create_estimate(req: CreateEstimateRequest) -> UnifiedEstimateResult:
    """Creates a transparent baseline, uncertainty range, and optional ML/analogy estimate."""
    result = generate_full_estimate(req)

    # Save to history
    record = {
        "estimate_id": f"est_{uuid.uuid4().hex[:8]}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "project_name": req.project_name,
        "currency": req.currency,
        "total_cost": result.baseline_estimate.total_project_cost,
        "direct_materials": result.baseline_estimate.direct_materials_cost,
        "direct_labor": result.baseline_estimate.direct_labor_cost,
        "ml_prediction": result.ml_prediction.get("prediction") if result.ml_prediction else None,
        "request_payload": req.model_dump()
    }
    history = _load_json_list(HISTORY_FILE)
    history.insert(0, record)
    _save_json_list(HISTORY_FILE, history[:50])  # keep last 50

    return result


@router.get("/history", response_model=List[Dict[str, Any]])
def get_estimate_history() -> List[Dict[str, Any]]:
    return _load_json_list(HISTORY_FILE)


@router.post("/actuals", response_model=Dict[str, str])
def record_actual_outcome(record: ActualOutcomeRecord) -> Dict[str, str]:
    """Records verified actual outcome of a completed project for audit and retraining (Rule R4 & 4.7)."""
    item = record.model_dump()
    if not item.get("recorded_at"):
        item["recorded_at"] = datetime.now(timezone.utc).isoformat()

    actuals = _load_json_list(ACTUALS_FILE)
    actuals.append(item)
    _save_json_list(ACTUALS_FILE, actuals)

    return {"message": f"Actual outcome recorded for project '{record.project_name}'."}


@router.get("/actuals", response_model=List[Dict[str, Any]])
def get_actual_outcomes() -> List[Dict[str, Any]]:
    return _load_json_list(ACTUALS_FILE)
