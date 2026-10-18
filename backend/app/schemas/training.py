"""Schemas for Training Jobs and Runs."""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class StartTrainingJobRequest(BaseModel):
    dataset_id: str
    target_column: str
    schema_template_name: Optional[str] = None
    split_strategy: str = Field(default="random", description="'random', 'time', or 'group'")
    time_column: Optional[str] = None
    group_column: Optional[str] = None
    random_seed: int = 42


class TrainingJobStatusResponse(BaseModel):
    job_id: str
    dataset_id: str
    target_column: str
    status: str  # "PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"
    progress_percentage: int
    started_at: str
    completed_at: Optional[str] = None
    logs: List[str]
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
