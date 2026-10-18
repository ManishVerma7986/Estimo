"""Dataset Ingestion Module.

Handles importing CSV, ARFF, Excel, and Parquet datasets, calculating cryptographic SHA-256
digests, extracting schema and data-quality summaries, and creating formal dataset manifests.
"""

from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


def compute_sha256(file_path: Path | str) -> str:
    """Computes SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_arff_file(path_str: str | Path) -> pd.DataFrame:
    """Robust parser for ARFF datasets."""
    text = Path(path_str).read_text(encoding="utf-8-sig", errors="replace")
    attrs: List[str] = []
    data_rows: List[List[str]] = []
    in_data = False

    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("%"):
            continue
        low = s.lower()
        if low.startswith("@attribute"):
            parts = re.split(r"[\s\t]+", s, maxsplit=2)
            if len(parts) >= 2:
                attrs.append(parts[1].strip("'\" "))
        elif low.startswith("@data"):
            in_data = True
        elif in_data:
            data_rows.append([v.strip().strip('"\'') for v in s.split(",")])

    n = len(attrs)
    clean: List[List[str]] = []
    for row in data_rows:
        if len(row) >= n:
            clean.append(row[:n])
        elif row and any(v.strip() for v in row):
            clean.append(row + [""] * (n - len(row)))

    df = pd.DataFrame(clean, columns=attrs)
    df = df.replace({"?": np.nan, "": np.nan})

    # Attempt to convert numeric columns
    for col in df.columns:
        try:
            df[col] = pd.to_numeric(df[col])
        except Exception:
            pass

    return df


def read_dataset_file(file_path: Path | str) -> pd.DataFrame:
    """Reads a dataset from CSV, ARFF, Excel, or Parquet."""
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".arff":
        return parse_arff_file(path)
    elif suffix == ".csv":
        # Check if separator is semicolon or comma
        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            first_line = f.readline()
        sep = ";" if first_line.count(";") > first_line.count(",") else ","
        decimal = "," if sep == ";" and "," in first_line else "."
        try:
            return pd.read_csv(path, sep=sep, decimal=decimal)
        except Exception:
            return pd.read_csv(path)
    elif suffix in [".xlsx", ".xls"]:
        return pd.read_excel(path)
    elif suffix == ".parquet":
        return pd.read_parquet(path)
    else:
        raise ValueError(f"Unsupported dataset format '{suffix}'. Allowed: .csv, .arff, .xlsx, .parquet")


def generate_data_quality_report(df: pd.DataFrame) -> Dict[str, Any]:
    """Generates an honest, automated data quality summary for a DataFrame."""
    total_rows = len(df)
    total_cols = len(df.columns)

    missing_per_col = df.isnull().sum().to_dict()
    missing_pct_per_col = (df.isnull().mean() * 100).round(2).to_dict()
    total_missing_cells = int(df.isnull().sum().sum())
    overall_missing_pct = round((total_missing_cells / max(total_rows * total_cols, 1)) * 100, 2)

    duplicate_rows = int(df.duplicated().sum())

    column_types: Dict[str, str] = {}
    numeric_stats: Dict[str, Any] = {}
    outlier_counts: Dict[str, int] = {}

    for col in df.columns:
        series = df[col]
        if pd.api.types.is_numeric_dtype(series):
            column_types[col] = "numeric"
            valid_s = series.dropna()
            if len(valid_s) > 0:
                q1 = float(valid_s.quantile(0.25))
                q3 = float(valid_s.quantile(0.75))
                iqr = q3 - q1
                outliers = int(((valid_s < q1 - 3 * iqr) | (valid_s > q3 + 3 * iqr)).sum())
                outlier_counts[col] = outliers
                numeric_stats[col] = {
                    "min": float(valid_s.min()),
                    "median": float(valid_s.median()),
                    "mean": float(valid_s.mean()),
                    "max": float(valid_s.max()),
                    "std": float(valid_s.std()) if len(valid_s) > 1 else 0.0,
                    "zeros": int((valid_s == 0).sum())
                }
        else:
            column_types[col] = "categorical"
            outlier_counts[col] = 0

    return {
        "total_rows": total_rows,
        "total_columns": total_cols,
        "duplicate_rows": duplicate_rows,
        "overall_missing_percentage": overall_missing_pct,
        "missing_per_column": missing_per_col,
        "missing_percentage_per_column": missing_pct_per_col,
        "column_types": column_types,
        "numeric_stats": numeric_stats,
        "extreme_outlier_counts_3iqr": outlier_counts,
        "sample_size_adequate_for_ml": total_rows >= 25,
        "sample_size_recommended": total_rows >= 50
    }


def ingest_dataset(
    file_path: Path | str,
    name: str,
    domain: str,
    license_type: str,
    source: str,
    notes: str = "",
    base_dir: Path | str = "."
) -> Dict[str, Any]:
    """Ingests a dataset into data/raw, produces data/processed, and records manifest."""
    base_path = Path(base_dir).resolve()
    raw_dir = base_path / "data" / "raw"
    processed_dir = base_path / "data" / "processed"
    manifests_dir = base_path / "data" / "manifests"

    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    manifests_dir.mkdir(parents=True, exist_ok=True)

    input_file = Path(file_path).resolve()
    if not input_file.exists():
        raise FileNotFoundError(f"Input file '{input_file}' not found.")

    sha256_hash = compute_sha256(input_file)
    dataset_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", name.lower()) + "_" + sha256_hash[:8]

    # Target raw storage directory
    target_raw_folder = raw_dir / dataset_id
    target_raw_folder.mkdir(parents=True, exist_ok=True)
    target_raw_file = target_raw_folder / input_file.name

    # Copy raw file unmodified
    shutil.copy2(input_file, target_raw_file)

    # Read and analyze data
    df = read_dataset_file(target_raw_file)
    quality_report = generate_data_quality_report(df)

    # Save to processed folder
    target_processed_folder = processed_dir / dataset_id
    target_processed_folder.mkdir(parents=True, exist_ok=True)
    processed_parquet = target_processed_folder / "data.parquet"
    processed_csv = target_processed_folder / "data.csv"

    # Save parquet and csv
    try:
        df.to_parquet(processed_parquet, index=False)
    except Exception:
        # Fallback if pyarrow/fastparquet issues arise
        df.to_pickle(target_processed_folder / "data.pkl")
    df.to_csv(processed_csv, index=False)

    # Column Schema representation
    schema_info = {
        col: {
            "type": quality_report["column_types"].get(col, "unknown"),
            "non_null_count": int(df[col].notnull().sum()),
            "unique_count": int(df[col].nunique())
        }
        for col in df.columns
    }

    manifest = {
        "dataset_id": dataset_id,
        "name": name,
        "domain": domain,
        "license": license_type,
        "source": source,
        "notes": notes,
        "ingestion_timestamp": datetime.now(timezone.utc).isoformat(),
        "original_filename": input_file.name,
        "raw_file_path": str(target_raw_file.relative_to(base_path)),
        "processed_file_path": str(processed_csv.relative_to(base_path)),
        "sha256": sha256_hash,
        "row_count": len(df),
        "column_count": len(df.columns),
        "columns": list(df.columns),
        "schema": schema_info,
        "quality_summary": quality_report
    }

    manifest_file = manifests_dir / f"{dataset_id}.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a dataset into the local dataset registry.")
    parser.add_argument("--file", required=True, help="Path to input dataset file (.csv, .arff, .xlsx, .parquet)")
    parser.add_argument("--name", required=True, help="Human-readable dataset name")
    parser.add_argument("--domain", default="software", help="Domain: software, building_products, or custom")
    parser.add_argument("--license", required=True, help="License/terms declaration (required by R1)")
    parser.add_argument("--source", required=True, help="Source URL or origin documentation")
    parser.add_argument("--notes", default="", help="Optional notes on methodology or provenance")
    parser.add_argument("--base-dir", default=".", help="Base project directory")

    args = parser.parse_args()

    try:
        manifest = ingest_dataset(
            file_path=args.file,
            name=args.name,
            domain=args.domain,
            license_type=args.license,
            source=args.source,
            notes=args.notes,
            base_dir=args.base_dir
        )
        print(f"SUCCESS: Dataset '{manifest['name']}' ingested successfully.")
        print(f"  Dataset ID: {manifest['dataset_id']}")
        print(f"  Rows: {manifest['row_count']} | Columns: {manifest['column_count']}")
        print(f"  SHA-256: {manifest['sha256']}")
        print(f"  Manifest: data/manifests/{manifest['dataset_id']}.json")
    except Exception as exc:
        print(f"ERROR: Ingestion failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
