"""Dataset Management Service.

Handles dataset manifests, quality analysis, schema templates, and deletions.
"""

from __future__ import annotations
import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from backend.app.core.config import settings
from backend.app.schemas.dataset import ColumnMappingTemplate, DatasetSummary
from ml.data_ingestion import ingest_dataset
from ml.preprocessing import detect_potential_leakage


class DatasetService:
    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or settings.base_dir
        self.manifests_dir = self.base_dir / "data" / "manifests"
        self.raw_dir = self.base_dir / "data" / "raw"
        self.processed_dir = self.base_dir / "data" / "processed"
        self.schemas_dir = self.base_dir / "configs" / "schemas"
        self.schemas_dir.mkdir(parents=True, exist_ok=True)

    def list_datasets(self) -> List[DatasetSummary]:
        if not self.manifests_dir.exists():
            return []
        datasets: List[DatasetSummary] = []
        for mf in self.manifests_dir.glob("*.json"):
            try:
                with open(mf, "r", encoding="utf-8") as f:
                    data = json.load(f)
                datasets.append(DatasetSummary(
                    dataset_id=data["dataset_id"],
                    name=data["name"],
                    domain=data.get("domain", "general"),
                    license=data.get("license", "Unknown"),
                    source=data.get("source", "Unknown"),
                    row_count=data.get("row_count", 0),
                    column_count=data.get("column_count", 0),
                    sha256=data.get("sha256", ""),
                    ingestion_timestamp=data.get("ingestion_timestamp", ""),
                    columns=data.get("columns", [])
                ))
            except Exception:
                continue
        return datasets

    def get_dataset_manifest(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        manifest_path = self.manifests_dir / f"{dataset_id}.json"
        if not manifest_path.exists():
            return None
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_quality_report(self, dataset_id: str, target_column: Optional[str] = None) -> Optional[Dict[str, Any]]:
        manifest = self.get_dataset_manifest(dataset_id)
        if not manifest:
            return None

        proc_path = self.base_dir / manifest["processed_file_path"]
        if proc_path.suffix == ".parquet" and proc_path.exists():
            df = pd.read_parquet(proc_path)
        else:
            df = pd.read_csv(proc_path.with_suffix(".csv"))

        leakage_warnings = []
        if target_column and target_column in df.columns:
            leakage_warnings = detect_potential_leakage(df, target_column)

        return {
            "dataset_id": dataset_id,
            "name": manifest["name"],
            "row_count": manifest["row_count"],
            "column_count": manifest["column_count"],
            "sha256": manifest["sha256"],
            "overall_missing_percentage": manifest.get("quality_summary", {}).get("overall_missing_percentage", 0.0),
            "duplicate_rows": manifest.get("quality_summary", {}).get("duplicate_rows", 0),
            "sample_size_adequate": manifest.get("quality_summary", {}).get("sample_size_adequate_for_ml", False),
            "quality_summary": manifest.get("quality_summary", {}),
            "potential_leakage_warnings": leakage_warnings
        }

    def delete_dataset(self, dataset_id: str) -> bool:
        manifest = self.get_dataset_manifest(dataset_id)
        if not manifest:
            return False

        # Remove raw folder
        raw_folder = self.raw_dir / dataset_id
        if raw_folder.exists():
            shutil.rmtree(raw_folder, ignore_errors=True)

        # Remove processed folder
        proc_folder = self.processed_dir / dataset_id
        if proc_folder.exists():
            shutil.rmtree(proc_folder, ignore_errors=True)

        # Remove manifest
        manifest_file = self.manifests_dir / f"{dataset_id}.json"
        if manifest_file.exists():
            manifest_file.unlink()

        return True

    # --- Schema Templates CRUD ---
    def save_schema_template(self, template: ColumnMappingTemplate) -> str:
        filename = f"{template.template_name}.json"
        target_path = self.schemas_dir / filename
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(template.model_dump(), f, indent=2)
        return template.template_name

    def list_schema_templates(self) -> List[ColumnMappingTemplate]:
        templates = []
        for tf in self.schemas_dir.glob("*.json"):
            try:
                with open(tf, "r", encoding="utf-8") as f:
                    templates.append(ColumnMappingTemplate(**json.load(f)))
            except Exception:
                continue
        return templates

    def get_schema_template(self, template_name: str) -> Optional[ColumnMappingTemplate]:
        tf = self.schemas_dir / f"{template_name}.json"
        if not tf.exists():
            return None
        with open(tf, "r", encoding="utf-8") as f:
            return ColumnMappingTemplate(**json.load(f))

    def delete_schema_template(self, template_name: str) -> bool:
        tf = self.schemas_dir / f"{template_name}.json"
        if tf.exists():
            tf.unlink()
            return True
        return False
