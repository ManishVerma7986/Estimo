"""Schemas for Dataset Management and Column Mapping."""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ColumnMappingTemplate(BaseModel):
    template_name: str
    domain: str = "software"
    target_column: str
    target_unit: str = "person-hours"
    feature_mappings: Dict[str, str] = Field(
        description="Dictionary of column_name -> column_type ('numeric', 'categorical', 'ordinal', 'date', 'ignore')"
    )
    units_and_currencies: Dict[str, str] = Field(default_factory=dict)
    notes: Optional[str] = None


class DatasetSummary(BaseModel):
    dataset_id: str
    name: str
    domain: str
    license: str
    source: str
    row_count: int
    column_count: int
    sha256: str
    ingestion_timestamp: str
    columns: List[str]


class DatasetQualityResponse(BaseModel):
    dataset_id: str
    name: str
    row_count: int
    column_count: int
    sha256: str
    overall_missing_percentage: float
    duplicate_rows: int
    sample_size_adequate: bool
    quality_summary: Dict[str, Any]
    potential_leakage_warnings: List[Dict[str, Any]]
