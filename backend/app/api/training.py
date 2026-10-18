"""Training Jobs API."""

from __future__ import annotations
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException

from backend.app.schemas.training import StartTrainingJobRequest, TrainingJobStatusResponse
from backend.app.services.training_service import training_manager

router = APIRouter(prefix="/training/jobs", tags=["Training"])


@router.post("", response_model=Dict[str, str])
def start_training_job(request: StartTrainingJobRequest) -> Dict[str, str]:
    job_id = training_manager.start_training_job(request)
    return {"job_id": job_id, "message": "Training job started in background worker."}


@router.get("", response_model=List[TrainingJobStatusResponse])
def list_training_jobs() -> List[TrainingJobStatusResponse]:
    return training_manager.list_jobs()


@router.get("/{job_id}", response_model=TrainingJobStatusResponse)
def get_job_status(job_id: str) -> TrainingJobStatusResponse:
    st = training_manager.get_job_status(job_id)
    if not st:
        raise HTTPException(status_code=404, detail=f"Training job '{job_id}' not found.")
    return st


@router.post("/{job_id}/cancel", response_model=Dict[str, str])
def cancel_job(job_id: str) -> Dict[str, str]:
    if training_manager.cancel_job(job_id):
        return {"message": f"Job '{job_id}' cancelled."}
    raise HTTPException(status_code=400, detail=f"Cannot cancel job '{job_id}' (it may already be completed or failed).")
