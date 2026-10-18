"""Report Export API (Excel, CSV, JSON)."""

from __future__ import annotations
import io
from pathlib import Path
from typing import Any, Dict, List
import pandas as pd
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse

from backend.app.core.config import settings
from backend.app.schemas.estimate import CreateEstimateRequest
from backend.app.services.cost_calculator import calculate_baseline_cost

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.post("/export/csv")
def export_estimate_csv(req: CreateEstimateRequest):
    """Exports itemised BOM and labor breakdown as CSV."""
    baseline = calculate_baseline_cost(req.bom_items, req.labor_items, req.rules)

    rows: List[Dict[str, Any]] = []
    for item in req.bom_items:
        rows.append({
            "Type": "BOM Item",
            "Category": item.category,
            "Description": item.item_name,
            "Quantity": item.quantity,
            "Unit": item.unit,
            "Unit_Price": item.unit_price,
            "Subtotal": round(item.quantity * item.unit_price, 2),
            "Currency": req.currency
        })

    for l in req.labor_items:
        rows.append({
            "Type": "Labor Role",
            "Category": "personnel",
            "Description": l.role_name,
            "Quantity": l.hours,
            "Unit": "person-hours",
            "Unit_Price": l.hourly_rate,
            "Subtotal": round(l.hours * l.hourly_rate * l.personnel_count, 2),
            "Currency": req.currency
        })

    df = pd.DataFrame(rows)
    stream = io.StringIO()
    df.to_csv(stream, index=False)

    return Response(
        content=stream.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{req.project_name}_estimate.csv"'}
    )


@router.post("/export/excel")
def export_estimate_excel(req: CreateEstimateRequest):
    """Exports comprehensive multi-sheet project estimate to Excel (.xlsx)."""
    baseline = calculate_baseline_cost(req.bom_items, req.labor_items, req.rules)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # Sheet 1: Summary
        summary_data = [
            {"Metric": "Project Name", "Value": req.project_name},
            {"Metric": "Currency", "Value": req.currency},
            {"Metric": "Direct Materials Cost", "Value": baseline.direct_materials_cost},
            {"Metric": "Direct Labor Cost", "Value": baseline.direct_labor_cost},
            {"Metric": "Direct Total Cost", "Value": baseline.direct_total_cost},
            {"Metric": f"Overhead ({baseline.overhead_percentage}%)", "Value": baseline.overhead_amount},
            {"Metric": f"Contingency ({baseline.contingency_percentage}%)", "Value": baseline.contingency_amount},
            {"Metric": f"Tax ({baseline.tax_percentage}%)", "Value": baseline.tax_amount},
            {"Metric": "TOTAL PROJECT COST", "Value": baseline.total_project_cost},
        ]
        pd.DataFrame(summary_data).to_excel(writer, sheet_name="Summary", index=False)

        # Sheet 2: BOM Items
        if req.bom_items:
            bom_rows = [b.model_dump() for b in req.bom_items]
            pd.DataFrame(bom_rows).to_excel(writer, sheet_name="Materials & Equipment", index=False)

        # Sheet 3: Labor
        if req.labor_items:
            labor_rows = [l.model_dump() for l in req.labor_items]
            pd.DataFrame(labor_rows).to_excel(writer, sheet_name="Personnel & Labor", index=False)

    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{req.project_name}_estimate.xlsx"'}
    )
