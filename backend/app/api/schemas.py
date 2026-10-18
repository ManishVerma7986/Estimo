"""Column Mapping Templates API."""

from __future__ import annotations
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException

from backend.app.schemas.dataset import ColumnMappingTemplate
from backend.app.services.dataset_service import DatasetService

router = APIRouter(prefix="/schemas", tags=["Schema Templates"])
dataset_service = DatasetService()


@router.get("", response_model=List[ColumnMappingTemplate])
def list_schema_templates() -> List[ColumnMappingTemplate]:
    return dataset_service.list_schema_templates()


@router.post("", response_model=Dict[str, str])
def save_schema_template(template: ColumnMappingTemplate) -> Dict[str, str]:
    name = dataset_service.save_schema_template(template)
    return {"message": f"Schema template '{name}' saved successfully."}


@router.get("/{template_name}", response_model=ColumnMappingTemplate)
def get_schema_template(template_name: str) -> ColumnMappingTemplate:
    tmpl = dataset_service.get_schema_template(template_name)
    if not tmpl:
        raise HTTPException(status_code=404, detail=f"Schema template '{template_name}' not found.")
    return tmpl


@router.delete("/{template_name}")
def delete_schema_template(template_name: str) -> Dict[str, str]:
    if dataset_service.delete_schema_template(template_name):
        return {"message": f"Schema template '{template_name}' deleted."}
    raise HTTPException(status_code=404, detail=f"Schema template '{template_name}' not found.")
