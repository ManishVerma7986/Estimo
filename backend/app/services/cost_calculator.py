"""Transparent Baseline Cost Calculator (Rule R1 & R2).

Zero ML required. Uses BOM arithmetic and labor role calculations with strictly traceable
user-entered or imported prices, configurable overheads, contingency, and tax rates.
Missing price => validation error, NEVER an invented guess.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class BOMItem(BaseModel):
    item_name: str
    quantity: float = Field(gt=0, description="Quantity of material or item")
    unit_price: float = Field(ge=0, description="Cost per unit")
    unit: str = Field(description="Unit of measurement (e.g., kg, sqft, piece, license)")
    currency: str = "INR"
    category: str = "materials"  # materials, equipment, software, licenses, infrastructure
    source: Optional[str] = None
    date: Optional[str] = None
    region: Optional[str] = None


class LaborItem(BaseModel):
    role_name: str
    hourly_rate: float = Field(gt=0, description="Cost per person-hour")
    hours: float = Field(gt=0, description="Estimated effort in person-hours")
    currency: str = "INR"
    personnel_count: int = Field(default=1, ge=1)
    notes: Optional[str] = None


class CalculationRules(BaseModel):
    overhead_percentage: float = Field(default=15.0, ge=0.0, le=100.0)
    contingency_percentage: float = Field(default=10.0, ge=0.0, le=100.0)
    tax_percentage: float = Field(default=18.0, ge=0.0, le=100.0)
    currency: str = "INR"


class CostBreakdownItem(BaseModel):
    category: str
    subtotal: float
    percentage_of_direct: float
    items_count: int


class BaselineCostReport(BaseModel):
    currency: str
    direct_materials_cost: float
    direct_labor_cost: float
    direct_total_cost: float
    overhead_amount: float
    overhead_percentage: float
    subtotal_with_overhead: float
    contingency_amount: float
    contingency_percentage: float
    subtotal_before_tax: float
    tax_amount: float
    tax_percentage: float
    total_project_cost: float
    breakdown_by_category: Dict[str, CostBreakdownItem]
    traceable_assumptions: List[str]


def calculate_baseline_cost(
    bom_items: List[BOMItem],
    labor_items: List[LaborItem],
    rules: Optional[CalculationRules] = None
) -> BaselineCostReport:
    """Calculates the transparent baseline cost from explicit user inputs."""
    calc_rules = rules or CalculationRules()
    currency = calc_rules.currency

    # 1. Validate BOM Items
    materials_cost = 0.0
    category_totals: Dict[str, float] = {}
    category_counts: Dict[str, int] = {}

    for item in bom_items:
        if item.unit_price is None or item.unit_price < 0:
            raise ValueError(f"Missing or invalid unit price for BOM item '{item.item_name}'. Rule R1: Never guess prices.")
        cost = round(item.quantity * item.unit_price, 2)
        materials_cost += cost
        cat = item.category.lower()
        category_totals[cat] = round(category_totals.get(cat, 0.0) + cost, 2)
        category_counts[cat] = category_counts.get(cat, 0) + 1

    # 2. Validate Labor Items
    labor_cost = 0.0
    total_labor_hours = 0.0
    for labor in labor_items:
        if labor.hourly_rate is None or labor.hourly_rate <= 0:
            raise ValueError(f"Missing or invalid hourly rate for labor role '{labor.role_name}'. Rule R1: Never guess rates.")
        cost = round(labor.hours * labor.hourly_rate * labor.personnel_count, 2)
        labor_cost += cost
        total_labor_hours += labor.hours * labor.personnel_count

    category_totals["personnel"] = round(labor_cost, 2)
    category_counts["personnel"] = len(labor_items)

    direct_total = round(materials_cost + labor_cost, 2)

    # 3. Apply Configurable Rules
    overhead_amt = round(direct_total * (calc_rules.overhead_percentage / 100.0), 2)
    subtotal_with_overhead = round(direct_total + overhead_amt, 2)

    contingency_amt = round(subtotal_with_overhead * (calc_rules.contingency_percentage / 100.0), 2)
    subtotal_before_tax = round(subtotal_with_overhead + contingency_amt, 2)

    tax_amt = round(subtotal_before_tax * (calc_rules.tax_percentage / 100.0), 2)
    grand_total = round(subtotal_before_tax + tax_amt, 2)

    # 4. Detailed Category Breakdown
    breakdown: Dict[str, CostBreakdownItem] = {}
    for cat, sub in category_totals.items():
        pct = round((sub / max(direct_total, 0.01)) * 100.0, 2) if direct_total > 0 else 0.0
        breakdown[cat] = CostBreakdownItem(
            category=cat,
            subtotal=sub,
            percentage_of_direct=pct,
            items_count=category_counts.get(cat, 0)
        )

    assumptions = [
        f"Base currency configured as {currency}.",
        f"Overhead computed as {calc_rules.overhead_percentage}% on total direct expenses ({direct_total:,.2f} {currency}).",
        f"Contingency buffer of {calc_rules.contingency_percentage}% applied on cost with overhead ({subtotal_with_overhead:,.2f} {currency}).",
        f"Tax/GST computed at {calc_rules.tax_percentage}% on pre-tax subtotal ({subtotal_before_tax:,.2f} {currency}).",
        f"Total estimated labor effort: {total_labor_hours:,.1f} person-hours across {len(labor_items)} defined role(s).",
        f"Total distinct BOM components: {len(bom_items)} item(s) totaling {materials_cost:,.2f} {currency}."
    ]

    return BaselineCostReport(
        currency=currency,
        direct_materials_cost=round(materials_cost, 2),
        direct_labor_cost=round(labor_cost, 2),
        direct_total_cost=direct_total,
        overhead_amount=overhead_amt,
        overhead_percentage=calc_rules.overhead_percentage,
        subtotal_with_overhead=subtotal_with_overhead,
        contingency_amount=contingency_amt,
        contingency_percentage=calc_rules.contingency_percentage,
        subtotal_before_tax=subtotal_before_tax,
        tax_amount=tax_amt,
        tax_percentage=calc_rules.tax_percentage,
        total_project_cost=grand_total,
        breakdown_by_category=breakdown,
        traceable_assumptions=assumptions
    )
