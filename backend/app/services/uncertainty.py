"""Monte Carlo Simulation and Sensitivity Analysis Module.

Performs reproducible Monte Carlo simulations with fixed, recorded random seeds
to compute P10, P50, P90 cost ranges and rank cost drivers by sensitivity.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from pydantic import BaseModel, Field

from backend.app.services.cost_calculator import BOMItem, CalculationRules, LaborItem


class SimulationVariable(BaseModel):
    name: str
    category: str  # "bom_item" or "labor_role"
    base_value: float
    uncertainty_percentage: float = Field(default=10.0, ge=0.0, le=100.0)
    distribution: str = "triangular"  # "triangular", "normal", "uniform"


class MonteCarloSimulationReport(BaseModel):
    iterations: int
    random_seed: int
    base_cost: float
    simulated_mean: float
    simulated_median_p50: float
    p10: float
    p25: float
    p75: float
    p90: float
    std_dev: float
    currency: str
    top_cost_drivers: List[Dict[str, Any]]
    confidence_80_range: Tuple[float, float]
    simulation_histogram: Dict[str, Any]


def run_monte_carlo_cost_simulation(
    bom_items: List[BOMItem],
    labor_items: List[LaborItem],
    rules: Optional[CalculationRules] = None,
    iterations: int = 2000,
    uncertainty_percentage: float = 15.0,
    random_seed: int = 42
) -> MonteCarloSimulationReport:
    """Runs a repeatable Monte Carlo simulation across BOM and labor components."""
    rng = np.random.RandomState(random_seed)
    calc_rules = rules or CalculationRules()
    currency = calc_rules.currency

    # Pre-compute base direct costs
    base_materials = sum(item.quantity * item.unit_price for item in bom_items)
    base_labor = sum(l.hours * l.hourly_rate * l.personnel_count for l in labor_items)
    base_direct = base_materials + base_labor
    overhead_mult = 1.0 + (calc_rules.overhead_percentage / 100.0)
    contingency_mult = 1.0 + (calc_rules.contingency_percentage / 100.0)
    tax_mult = 1.0 + (calc_rules.tax_percentage / 100.0)
    total_multiplier = overhead_mult * contingency_mult * tax_mult

    base_total = round(base_direct * total_multiplier, 2)

    # Prepare arrays for simulation
    simulated_totals = np.zeros(iterations)
    item_variances: Dict[str, float] = {}

    # Sample variation per BOM item
    bom_sims = np.zeros((len(bom_items), iterations))
    for i, item in enumerate(bom_items):
        mean_val = item.quantity * item.unit_price
        u = uncertainty_percentage / 100.0
        # Triangular distribution around base (low = base*(1-u), mode = base, high = base*(1+u))
        samples = rng.triangular(mean_val * (1 - u), mean_val, mean_val * (1 + u), size=iterations)
        bom_sims[i] = samples
        item_variances[f"BOM: {item.item_name}"] = float(np.var(samples))

    # Sample variation per Labor role
    labor_sims = np.zeros((len(labor_items), iterations))
    for j, labor in enumerate(labor_items):
        mean_val = labor.hours * labor.hourly_rate * labor.personnel_count
        u = uncertainty_percentage / 100.0
        samples = rng.triangular(mean_val * (1 - u), mean_val, mean_val * (1 + u), size=iterations)
        labor_sims[j] = samples
        item_variances[f"Labor: {labor.role_name}"] = float(np.var(samples))

    # Aggregate total costs per iteration
    total_materials_sims = np.sum(bom_sims, axis=0) if len(bom_items) > 0 else np.zeros(iterations)
    total_labor_sims = np.sum(labor_sims, axis=0) if len(labor_items) > 0 else np.zeros(iterations)
    direct_sims = total_materials_sims + total_labor_sims

    simulated_totals = direct_sims * total_multiplier

    # Percentiles
    p10 = float(np.percentile(simulated_totals, 10))
    p25 = float(np.percentile(simulated_totals, 25))
    p50 = float(np.percentile(simulated_totals, 50))
    p75 = float(np.percentile(simulated_totals, 75))
    p90 = float(np.percentile(simulated_totals, 90))
    mean_val = float(np.mean(simulated_totals))
    std_val = float(np.std(simulated_totals))

    # Top drivers by variance contribution (sensitivity)
    total_var = sum(item_variances.values()) or 1.0
    sorted_drivers = sorted(item_variances.items(), key=lambda x: x[1], reverse=True)
    top_drivers = [
        {
            "name": name,
            "variance_contribution_pct": round((var / total_var) * 100.0, 2),
            "std_deviation": round(float(np.sqrt(var) * total_multiplier), 2)
        }
        for name, var in sorted_drivers[:10]
    ]

    # Histogram binning for charting
    hist_counts, bin_edges = np.histogram(simulated_totals, bins=20)
    histogram_data = {
        "bins": [round(float(b), 2) for b in bin_edges],
        "counts": [int(c) for c in hist_counts]
    }

    return MonteCarloSimulationReport(
        iterations=iterations,
        random_seed=random_seed,
        base_cost=base_total,
        simulated_mean=round(mean_val, 2),
        simulated_median_p50=round(p50, 2),
        p10=round(p10, 2),
        p25=round(p25, 2),
        p75=round(p75, 2),
        p90=round(p90, 2),
        std_dev=round(std_val, 2),
        currency=currency,
        top_cost_drivers=top_drivers,
        confidence_80_range=(round(p10, 2), round(p90, 2)),
        simulation_histogram=histogram_data
    )
