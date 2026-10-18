"""Model Training Pipeline Module.

Trains candidate models (Ridge, HistGradientBoosting / XGBoost, RandomForest, Huber, Baseline),
evaluates them on held-out test splits, tests against approval gates,
and persists versioned artifacts to models/<target>/<version>/ with SHA-256 checksums.
"""

from __future__ import annotations
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import HuberRegressor, Ridge
from sklearn.neighbors import KNeighborsRegressor

from ml.evaluate import check_approval_gate, compute_metrics
from ml.preprocessing import (
    build_preprocessor_pipeline,
    detect_potential_leakage,
    split_data,
)
from ml.registry import ModelRegistry

try:
    import xgboost as xgb
    XGB_AVAILABLE = True
except ImportError:
    XGB_AVAILABLE = False


from ml.pipeline import FullEstimationPipeline, MedianBaselineEstimator


def train_models_for_dataset(
    dataset_id: str,
    target_column: str,
    schema_template_path: Optional[str] = None,
    split_strategy: str = "random",
    test_size: float = 0.20,
    time_column: Optional[str] = None,
    group_column: Optional[str] = None,
    random_seed: int = 42,
    base_dir: Path | str = "."
) -> Dict[str, Any]:
    """Runs a complete training run on a registered dataset."""
    base_path = Path(base_dir).resolve()
    manifest_file = base_path / "data" / "manifests" / f"{dataset_id}.json"
    if not manifest_file.exists():
        raise FileNotFoundError(f"Manifest for dataset '{dataset_id}' not found at {manifest_file}")

    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # Load data
    processed_path = base_path / manifest["processed_file_path"]
    if processed_path.suffix == ".parquet" and processed_path.exists():
        df = pd.read_parquet(processed_path)
    else:
        csv_path = processed_path.with_suffix(".csv")
        df = pd.read_csv(csv_path)

    # Clean target
    if target_column not in df.columns:
        raise ValueError(f"Target column '{target_column}' does not exist in dataset. Columns: {list(df.columns)}")

    df[target_column] = pd.to_numeric(df[target_column], errors="coerce")
    df = df.dropna(subset=[target_column])
    df = df[df[target_column] > 0].reset_index(drop=True)

    n_rows = len(df)
    if n_rows < 10:
        raise ValueError(f"Dataset has only {n_rows} rows with valid target values, cannot train.")

    # Leakage check
    leakage_warnings = detect_potential_leakage(df, target_column)
    leaking_cols = {w["column"] for w in leakage_warnings if w.get("severity") == "CRITICAL"}
    if leaking_cols:
        print(f"  [Leakage Guard] Automatically dropping critical leaking columns: {leaking_cols}")
        df = df.drop(columns=list(leaking_cols))

    # Schema mapping
    feature_types: Dict[str, str] = {}
    if schema_template_path and Path(schema_template_path).exists():
        with open(schema_template_path, "r", encoding="utf-8") as sf:
            feature_types = json.load(sf)
    else:
        # Auto-detect numeric vs categorical
        id_terms = {"id", "project", "project_id", "project_no", "projct", "recordnumber", "projectname", "row_id"}
        for col in df.columns:
            if col == target_column:
                continue
            if col.lower() in id_terms:
                continue
            if pd.api.types.is_numeric_dtype(df[col]):
                feature_types[col] = "numeric"
            else:
                feature_types[col] = "categorical"

    feature_cols = [c for c in feature_types if c in df.columns]

    # Split dataset
    df_train, df_test = split_data(
        df=df,
        target_column=target_column,
        split_strategy=split_strategy,
        test_size=test_size,
        time_column=time_column,
        group_column=group_column,
        random_seed=random_seed
    )

    X_train = df_train[feature_cols]
    y_train = df_train[target_column].values
    X_test = df_test[feature_cols]
    y_test = df_test[target_column].values

    # Preprocessor
    preprocessor, num_cols, cat_cols = build_preprocessor_pipeline(feature_types, target_column)

    # 1. Fit baseline calculator
    baseline = MedianBaselineEstimator()
    baseline.fit(X_train, y_train)
    y_pred_baseline = baseline.predict(X_test)
    baseline_metrics = compute_metrics(y_test, y_pred_baseline)

    candidates: Dict[str, Tuple[Any, bool]] = {
        "Ridge": (Ridge(alpha=10.0), True),
        "Huber": (HuberRegressor(epsilon=1.35, max_iter=500), True),
        "RandomForest": (RandomForestRegressor(n_estimators=200, min_samples_leaf=2, random_state=random_seed, n_jobs=-1), True),
        "HistGradBoost": (HistGradientBoostingRegressor(max_iter=200, random_state=random_seed), True),
    }
    if XGB_AVAILABLE:
        candidates["XGBoost"] = (xgb.XGBRegressor(n_estimators=200, max_depth=4, learning_rate=0.05, random_state=random_seed, verbosity=0), True)

    results: List[Dict[str, Any]] = [{
        "algorithm": "Median_Baseline",
        "status": "BASELINE",
        "reasons": [],
        "metrics": baseline_metrics
    }]

    gate_cfg = base_path / "configs" / "evaluation_gates.json"
    registry = ModelRegistry(base_dir=base_path)
    version = datetime.now(timezone.utc).strftime("v%Y%m%d_%H%M%S")

    best_candidate_name: Optional[str] = None
    best_candidate_pipeline: Optional[FullEstimationPipeline] = None
    best_candidate_metrics: Optional[Dict[str, Any]] = None
    best_candidate_status: str = "REJECTED"
    lowest_mae = baseline_metrics["MAE"]

    for name, (estimator, use_log) in candidates.items():
        try:
            # Build fresh preprocessor per candidate
            prep, _, _ = build_preprocessor_pipeline(feature_types, target_column)
            pipe = FullEstimationPipeline(prep, estimator, use_log_target=use_log)
            pipe.fit(X_train, y_train)
            y_pred = pipe.predict(X_test)
            metrics = compute_metrics(y_test, y_pred)

            status, reasons = check_approval_gate(
                candidate_metrics=metrics,
                baseline_mae=baseline_metrics["MAE"],
                total_dataset_rows=n_rows,
                gate_config_path=gate_cfg
            )

            results.append({
                "algorithm": name,
                "status": status,
                "reasons": reasons,
                "metrics": metrics
            })

            # Check if this is the best so far
            if status in ["APPROVED", "EXPERIMENTAL"] and metrics["MAE"] < lowest_mae:
                lowest_mae = metrics["MAE"]
                best_candidate_name = name
                best_candidate_pipeline = pipe
                best_candidate_metrics = metrics
                best_candidate_status = status

        except Exception as e:
            results.append({
                "algorithm": name,
                "status": "ERROR",
                "reasons": [str(e)],
                "metrics": {}
            })

    # Save artifact if approved or experimental
    saved_model_info = None
    if best_candidate_pipeline is not None and best_candidate_name is not None:
        target_dir = base_path / "models" / target_column / version
        target_dir.mkdir(parents=True, exist_ok=True)

        model_file = target_dir / "model.joblib"
        joblib.dump(best_candidate_pipeline, model_file)

        metadata_file = target_dir / "metadata.json"
        metadata = {
            "algorithm": best_candidate_name,
            "target": target_column,
            "version": version,
            "dataset_id": dataset_id,
            "status": best_candidate_status,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "random_seed": random_seed,
            "split_strategy": split_strategy,
            "train_rows": len(df_train),
            "test_rows": len(df_test)
        }
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        eval_file = target_dir / "evaluation.json"
        with open(eval_file, "w", encoding="utf-8") as f:
            json.dump(best_candidate_metrics, f, indent=2)

        schema_file = target_dir / "feature_schema.json"
        with open(schema_file, "w", encoding="utf-8") as f:
            json.dump({
                "target": target_column,
                "features": feature_types,
                "numeric_features": num_cols,
                "categorical_features": cat_cols
            }, f, indent=2)

        manifest_copy_file = target_dir / "dataset_manifest.json"
        with open(manifest_copy_file, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        # Register in models/registry.json
        model_key = registry.register_model(
            target=target_column,
            version=version,
            model_file_rel_path=str(model_file.relative_to(base_path)),
            metadata_file_rel_path=str(metadata_file.relative_to(base_path)),
            evaluation_file_rel_path=str(eval_file.relative_to(base_path)),
            feature_schema_file_rel_path=str(schema_file.relative_to(base_path)),
            dataset_manifest_rel_path=str(manifest_copy_file.relative_to(base_path)),
            dataset_id=dataset_id,
            algorithm=best_candidate_name,
            status=best_candidate_status,
            metrics=best_candidate_metrics or {}
        )
        saved_model_info = {"model_key": model_key, "version": version, "algorithm": best_candidate_name}

    return {
        "dataset_id": dataset_id,
        "target": target_column,
        "total_rows": n_rows,
        "baseline_mae": baseline_metrics["MAE"],
        "candidates": results,
        "saved_model": saved_model_info
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and evaluate cost estimation models.")
    parser.add_argument("--dataset", required=True, help="Dataset ID (as recorded in data/manifests)")
    parser.add_argument("--target", required=True, help="Target column name (e.g., Effort, cost, actual)")
    parser.add_argument("--schema", default=None, help="Optional schema template JSON path")
    parser.add_argument("--split", default="random", choices=["random", "time", "group"], help="Splitting strategy")
    parser.add_argument("--base-dir", default=".", help="Base project directory")

    args = parser.parse_args()

    try:
        res = train_models_for_dataset(
            dataset_id=args.dataset,
            target_column=args.target,
            schema_template_path=args.schema,
            split_strategy=args.split,
            base_dir=args.base_dir
        )
        print("\n" + "=" * 65)
        print(f"  TRAINING RESULTS: {res['dataset_id']} (target: {res['target']})")
        print("=" * 65)
        for c in res["candidates"]:
            status = c["status"]
            alg = c["algorithm"]
            m = c.get("metrics", {})
            mae = m.get("MAE", "-")
            p25 = m.get("PRED25", "-")
            mmre = m.get("MMRE", "-")
            reason_str = "; ".join(c.get("reasons", []))
            print(f"  {status:<13} {alg:<18} MAE={mae:<8} PRED25={p25:<8} MMRE={mmre:<8}" + (f" ({reason_str})" if reason_str else ""))
        print("-" * 65)
        if res["saved_model"]:
            print(f"SUCCESS: Approved model saved and registered: {res['saved_model']['model_key']}")
        else:
            print("INFO: No candidate passed the approval gate. Baseline remains active.")
        print()

    except Exception as exc:
        print(f"ERROR: Training failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
