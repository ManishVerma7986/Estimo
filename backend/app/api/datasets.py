"""Datasets Management API."""

from __future__ import annotations
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from backend.app.core.security import validate_dataset_upload
from backend.app.schemas.dataset import DatasetQualityResponse, DatasetSummary
from backend.app.services.dataset_service import DatasetService
from ml.data_ingestion import ingest_dataset

router = APIRouter(prefix="/datasets", tags=["Datasets"])
dataset_service = DatasetService()


@router.get("", response_model=List[DatasetSummary])
def list_all_datasets() -> List[DatasetSummary]:
    """Lists all registered datasets with manifests."""
    return dataset_service.list_datasets()


@router.post("/upload", response_model=Dict[str, Any])
async def upload_dataset(
    file: UploadFile = File(...),
    name: str = Form(...),
    domain: str = Form(default="software"),
    license: str = Form(..., description="Required license / provenance terms (Rule R1)"),
    source: str = Form(..., description="Source URL or physical document origin"),
    notes: Optional[str] = Form(default="")
) -> Dict[str, Any]:
    """Uploads and ingests a dataset, computing SHA-256 and creating manifest."""
    clean_name, suffix = validate_dataset_upload(file)

    # Save to temp location first
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        manifest = ingest_dataset(
            file_path=tmp_path,
            name=name,
            domain=domain,
            license_type=license,
            source=source,
            notes=notes or ""
        )
        return manifest
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


@router.get("/{dataset_id}/manifest")
def get_dataset_manifest(dataset_id: str) -> Dict[str, Any]:
    manifest = dataset_service.get_dataset_manifest(dataset_id)
    if not manifest:
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found.")
    return manifest


@router.get("/{dataset_id}/quality-report", response_model=DatasetQualityResponse)
def get_dataset_quality_report(dataset_id: str, target: Optional[str] = None) -> DatasetQualityResponse:
    report = dataset_service.get_quality_report(dataset_id, target_column=target)
    if not report:
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found.")
    return DatasetQualityResponse(**report)


@router.delete("/{dataset_id}")
def delete_dataset(dataset_id: str) -> Dict[str, Any]:
    success = dataset_service.delete_dataset(dataset_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found.")
    return {"message": f"Dataset '{dataset_id}' successfully deleted."}
