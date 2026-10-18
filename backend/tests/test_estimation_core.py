"""Automated Test Suite: Baseline Cost Calculator, BOM Arithmetic, Uncertainty, and Scenarios."""

import pytest
from backend.app.services.cost_calculator import (
    calculate_baseline_cost,
    BOMItem,
    CalculationRules,
    LaborItem,
)
from backend.app.services.uncertainty import run_monte_carlo_cost_simulation
from backend.app.services.estimation import (
    compare_scenarios,
    generate_full_estimate,
    EstimationRequest,
)


def test_bom_and_labor_arithmetic_correctness():
    """Verifies that direct costs, overheads, contingency, and taxes calculate with exact precision."""
    bom_items = [
        BOMItem(item_name="Structural Steel", quantity=100.0, unit_price=65.50, unit="kg", currency="INR"),
        BOMItem(item_name="Reinforced Concrete", quantity=50.0, unit_price=420.00, unit="bag", currency="INR"),
    ]
    labor_items = [
        LaborItem(role_name="Senior Engineer", hourly_rate=1200.0, hours=40.0, currency="INR", personnel_count=1),
        LaborItem(role_name="Technician", hourly_rate=500.0, hours=80.0, currency="INR", personnel_count=2),  # 80 * 500 * 2 = 80,000
    ]
    rules = CalculationRules(
        overhead_percentage=15.0,
        contingency_percentage=10.0,
        tax_percentage=18.0,
        currency="INR"
    )

    # Manual expected values:
    # Materials = (100 * 65.50) + (50 * 420.00) = 6,550 + 21,000 = 27,550.00
    # Labor = (40 * 1200) + (80 * 500 * 2) = 48,000 + 80,000 = 128,000.00
    # Direct total = 27,550 + 128,000 = 155,550.00
    # Overhead (15%) = 155,550 * 0.15 = 23,332.50
    # Subtotal with overhead = 178,882.50
    # Contingency (10%) = 178,882.50 * 0.10 = 17,888.25
    # Subtotal before tax = 196,770.75
    # Tax (18%) = 196,770.75 * 0.18 = 35,418.735 -> 35,418.74
    # Grand Total = 196,770.75 + 35,418.74 = 232,189.49

    report = calculate_baseline_cost(bom_items, labor_items, rules)

    assert report.direct_materials_cost == 27550.00
    assert report.direct_labor_cost == 128000.00
    assert report.direct_total_cost == 155550.00
    assert report.overhead_amount == 23332.50
    assert report.subtotal_with_overhead == 178882.50
    assert report.contingency_amount == 17888.25
    assert report.subtotal_before_tax == 196770.75
    assert report.tax_amount == 35418.74
    assert report.total_project_cost == 232189.49
    assert report.currency == "INR"
    assert len(report.traceable_assumptions) >= 4


def test_missing_price_raises_validation_error():
    """Rule R1: Missing or invalid prices must raise a validation error, never an invented guess."""
    with pytest.raises(Exception):
        BOMItem(item_name="Incomplete Item", quantity=10, unit_price=-5.0, unit="units")


def test_monte_carlo_reproducibility():
    """Verifies that Monte Carlo with the same fixed seed produces identical deterministic distributions."""
    bom_items = [
        BOMItem(item_name="Component X", quantity=20.0, unit_price=500.0, unit="piece", currency="INR")
    ]
    labor_items = [
        LaborItem(role_name="Developer", hourly_rate=800.0, hours=50.0, currency="INR")
    ]
    rules = CalculationRules(currency="INR")

    run1 = run_monte_carlo_cost_simulation(bom_items, labor_items, rules, iterations=500, random_seed=42)
    run2 = run_monte_carlo_cost_simulation(bom_items, labor_items, rules, iterations=500, random_seed=42)

    assert run1.p10 == run2.p10
    assert run1.simulated_median_p50 == run2.simulated_median_p50
    assert run1.p90 == run2.p90
    assert run1.std_dev == run2.std_dev
    assert run1.p10 < run1.simulated_median_p50 < run1.p90


def test_what_if_scenario_comparison():
    """Verifies side-by-side what-if scenario delta calculations."""
    req = EstimationRequest(
        project_name="Base Project",
        currency="INR",
        bom_items=[BOMItem(item_name="Raw Metal", quantity=100.0, unit_price=100.0, unit="kg", currency="INR")],
        labor_items=[LaborItem(role_name="Machinist", hourly_rate=500.0, hours=100.0, currency="INR")],
        rules=CalculationRules(overhead_percentage=10.0, contingency_percentage=5.0, tax_percentage=18.0)
    )

    variations = {
        "High Labor (+20%)": {"labor_rate_multiplier": 1.20},
        "High Contingency (15%)": {"contingency_percentage": 15.0}
    }

    report = compare_scenarios(req, variations)
    assert len(report.scenarios) == 2
    high_labor = next(s for s in report.scenarios if s.scenario_name == "High Labor (+20%)")
    assert high_labor.cost_difference_vs_baseline > 0
    assert high_labor.percentage_change > 0
