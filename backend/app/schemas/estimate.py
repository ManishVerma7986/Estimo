"""Schemas for Cost Estimation Requests and History."""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.app.services.cost_calculator import BOMItem, CalculationRules, LaborItem


class CreateEstimateRequest(BaseModel):
    project_name: str
    currency: str = "INR"
    bom_items: List[BOMItem] = Field(default_factory=list)
    labor_items: List[LaborItem] = Field(default_factory=list)
    rules: Optional[CalculationRules] = None
    ml_features: Optional[Dict[str, Any]] = None
    target_metric: str = "Effort"
    analogy_dataset_id: Optional[str] = None


class ActualOutcomeRecord(BaseModel):
    estimate_id: Optional[str] = None
    project_name: str
    target_metric: str
    predicted_value: Optional[float] = None
    actual_value: float = Field(gt=0, description="Verified actual outcome")
    actual_cost: Optional[float] = None
    actual_hours: Optional[float] = None
    recorded_at: Optional[str] = None
    notes: Optional[str] = None
