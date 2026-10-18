"""What-If Scenario Planning API."""

from __future__ import annotations
from typing import Any, Dict, List
from fastapi import APIRouter
from pydantic import BaseModel

from backend.app.schemas.estimate import CreateEstimateRequest
from backend.app.services.estimation import compare_scenarios, ScenarioComparisonReport

router = APIRouter(prefix="/scenarios", tags=["Scenarios"])


class ScenarioComparePayload(BaseModel):
    base_project: CreateEstimateRequest
    what_if_scenarios: Dict[str, Dict[str, Any]]


@router.post("/compare", response_model=ScenarioComparisonReport)
def run_scenario_comparison(payload: ScenarioComparePayload) -> ScenarioComparisonReport:
    """Computes side-by-side cost impact of varying rates, quantities, overheads, and contingency."""
    return compare_scenarios(payload.base_project, payload.what_if_scenarios)
