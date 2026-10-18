"""Application Settings and Core Configuration."""

from __future__ import annotations
import json
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Estimo 3.0 Cost Engine"
    app_version: str = "1.0.0"
    api_prefix: str = "/api"
    default_currency: str = "INR"
    cors_origins: List[str] = ["*"]
    base_dir: Path = Path(__file__).resolve().parent.parent.parent.parent

    # Storage paths
    data_raw_dir: Path = base_dir / "data" / "raw"
    data_processed_dir: Path = base_dir / "data" / "processed"
    data_manifests_dir: Path = base_dir / "data" / "manifests"
    models_dir: Path = base_dir / "models"
    reports_dir: Path = base_dir / "reports"
    configs_dir: Path = base_dir / "configs"

    # Security limits
    max_upload_size_bytes: int = 50 * 1024 * 1024  # 50 MB
    allowed_dataset_extensions: List[str] = [".csv", ".arff", ".xlsx", ".parquet"]
    prohibited_extensions: List[str] = [
        ".exe", ".bat", ".cmd", ".sh", ".py", ".joblib", ".pkl", ".pickle", ".dll", ".so"
    ]

    class Config:
        env_prefix = "ESTIMO_"


settings = Settings()
