"""Unified Estimation and Scenario Planning Service.

Orchestrates transparent baseline arithmetic, historical analogy matching,
offline ML inference, and side-by-side what-if scenario comparison.
"""

from __future__ import annotations
import copy
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.app.core.config import settings
from backend.app.services.analogy import estimate_by_analogy, AnalogyEstimateReport
from backend.app.services.cost_calculator import (
    calculate_baseline_cost,
    BaselineCostReport,
    BOMItem,
    CalculationRules,
    LaborItem,
)
from backend.app.services.uncertainty import (
    run_monte_carlo_cost_simulation,
    MonteCarloSimulationReport,
)
from ml.predict import predict_cost


class EstimationRequest(BaseModel):
    project_name: str
    currency: str = "INR"
    bom_items: List[BOMItem] = Field(default_factory=list)
    labor_items: List[LaborItem] = Field(default_factory=list)
    rules: Optional[CalculationRules] = None
    ml_features: Optional[Dict[str, Any]] = None
    target_metric: str = "Effort"
    analogy_dataset_id: Optional[str] = None


class UnifiedEstimateResult(BaseModel):
    project_name: str
    currency: str
    baseline_estimate: BaselineCostReport
    monte_carlo_uncertainty: Optional[MonteCarloSimulationReport] = None
    ml_prediction: Optional[Dict[str, Any]] = None
    analogy_estimate: Optional[AnalogyEstimateReport] = None


class ScenarioDelta(BaseModel):
    scenario_name: str
    total_cost: float
    cost_difference_vs_baseline: float
    percentage_change: float
    summary: str


class ScenarioComparisonReport(BaseModel):
    baseline_scenario: BaselineCostReport
    scenarios: List[ScenarioDelta]


def generate_full_estimate(request: EstimationRequest) -> UnifiedEstimateResult:
    """Executes baseline, simulation, and optional analogy/ML estimation."""
    rules = request.rules or CalculationRules(currency=request.currency)
    rules.currency = request.currency

    # 1. Baseline calculation
    baseline = calculate_baseline_cost(request.bom_items, request.labor_items, rules)

    # 2. Monte Carlo simulation
    simulation = None
    if len(request.bom_items) > 0 or len(request.labor_items) > 0:
        simulation = run_monte_carlo_cost_simulation(
            bom_items=request.bom_items,
            labor_items=request.labor_items,
            rules=rules
        )

    # 3. ML prediction (if features provided)
    ml_res = None
    if request.ml_features:
        ml_res = predict_cost(
            target=request.target_metric,
            features=request.ml_features,
            dataset_id=request.analogy_dataset_id,
            base_dir=settings.base_dir
        )

    # 4. Analogy estimation (if dataset specified)
    analogy_res = None
    if request.analogy_dataset_id and request.ml_features:
        try:
            analogy_res = estimate_by_analogy(
                query_features=request.ml_features,
                dataset_id=request.analogy_dataset_id,
                target_column=request.target_metric
            )
        except Exception:
            pass

    return UnifiedEstimateResult(
        project_name=request.project_name,
        currency=request.currency,
        baseline_estimate=baseline,
        monte_carlo_uncertainty=simulation,
        ml_prediction=ml_res,
        analogy_estimate=analogy_res
    )


def compare_scenarios(
    base_request: EstimationRequest,
    what_if_variations: Dict[str, Dict[str, Any]]
) -> ScenarioComparisonReport:
    """Computes side-by-side what-if scenarios on rates, quantities, contingency, etc."""
    base_rules = base_request.rules or CalculationRules(currency=base_request.currency)
    base_baseline = calculate_baseline_cost(base_request.bom_items, base_request.labor_items, base_rules)
    base_total = base_baseline.total_project_cost

    scenario_deltas: List[ScenarioDelta] = []

    for name, delta_params in what_if_variations.items():
        var_bom = copy.deepcopy(base_request.bom_items)
        var_labor = copy.deepcopy(base_request.labor_items)
        var_rules = copy.deepcopy(base_rules)

        # Apply multiplier or override deltas
        labor_rate_multiplier = delta_params.get("labor_rate_multiplier", 1.0)
        bom_quantity_multiplier = delta_params.get("bom_quantity_multiplier", 1.0)
        bom_price_multiplier = delta_params.get("bom_price_multiplier", 1.0)

        if "contingency_percentage" in delta_params:
            var_rules.contingency_percentage = float(delta_params["contingency_percentage"])
        if "overhead_percentage" in delta_params:
            var_rules.overhead_percentage = float(delta_params["overhead_percentage"])

        for b in var_bom:
            b.quantity = round(b.quantity * bom_quantity_multiplier, 3)
            b.unit_price = round(b.unit_price * bom_price_multiplier, 2)

        for l in var_labor:
            l.hourly_rate = round(l.hourly_rate * labor_rate_multiplier, 2)

        var_baseline = calculate_baseline_cost(var_bom, var_labor, var_rules)
        diff = round(var_baseline.total_project_cost - base_total, 2)
        pct = round((diff / max(base_total, 0.01)) * 100.0, 2)

        scenario_deltas.append(ScenarioDelta(
            scenario_name=name,
            total_cost=var_baseline.total_project_cost,
            cost_difference_vs_baseline=diff,
            percentage_change=pct,
            summary=f"Cost difference: {diff:+,.2f} {base_rules.currency} ({pct:+.1f}%)"
        ))

    return ScenarioComparisonReport(
        baseline_scenario=base_baseline,
        scenarios=scenario_deltas
    )
