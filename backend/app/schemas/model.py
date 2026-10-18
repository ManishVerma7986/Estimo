"""Schemas for Model Registry and Activation."""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ModelItem(BaseModel):
    model_key: str
    target: str
    version: str
    algorithm: str
    dataset_id: str
    status: str
    is_active: bool
    sha256: str
    metrics: Dict[str, Any]
    registered_at: str


class ActivateModelRequest(BaseModel):
    target: str
    version: str


class RollbackModelRequest(BaseModel):
    target: str


class ModelHealthReport(BaseModel):
    status: str
    models_available: bool
    active_models_count: int
    active_models: Dict[str, str]
    checksum_verification: Dict[str, bool]
    offline_capable: bool
