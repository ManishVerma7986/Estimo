"""Analogy-Based Estimation (ABE) Engine.

Retrieves similar historical projects from the user's imported datasets,
calculates feature-scaled distances, and reports analogy coverage and similarity.
Refuses to estimate if insufficient comparable historical projects exist (Rule R2).
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from sklearn.preprocessing import StandardScaler


class SimilarProject(BaseModel):
    project_index: int
    similarity_score_pct: float
    distance: float
    actual_target_value: float
    target_unit: str
    features: Dict[str, Any]


class AnalogyEstimateReport(BaseModel):
    status: str  # "SUCCESS" or "INSUFFICIENT_ANALOGIES"
    target: str
    target_unit: str
    k_analogies: int
    analogy_coverage_pct: float
    mean_similarity_pct: float
    point_estimate: Optional[float]
    low_estimate: Optional[float]
    high_estimate: Optional[float]
    similar_projects: List[SimilarProject]
    notes: List[str]


def estimate_by_analogy(
    query_features: Dict[str, Any],
    dataset_id: str,
    target_column: str,
    k: int = 3,
    min_similarity_threshold: float = 40.0,
    base_dir: Path | str = "."
) -> AnalogyEstimateReport:
    """Finds nearest historical analogies from user-imported dataset."""
    base_path = Path(base_dir).resolve()
    manifest_path = base_path / "data" / "manifests" / f"{dataset_id}.json"

    if not manifest_path.exists():
        repo_root = Path(__file__).resolve().parents[3]
        if (repo_root / "data" / "manifests" / f"{dataset_id}.json").exists():
            base_path = repo_root
            manifest_path = base_path / "data" / "manifests" / f"{dataset_id}.json"
        else:
            raise FileNotFoundError(f"Manifest for dataset '{dataset_id}' not found.")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # Read processed data
    proc_path = base_path / manifest["processed_file_path"]
    if proc_path.suffix == ".parquet" and proc_path.exists():
        df = pd.read_parquet(proc_path)
    else:
        df = pd.read_csv(proc_path.with_suffix(".csv"))

    if target_column not in df.columns:
        raise ValueError(f"Target column '{target_column}' not found in dataset '{dataset_id}'.")

    # Clean target
    df[target_column] = pd.to_numeric(df[target_column], errors="coerce")
    valid_df = df.dropna(subset=[target_column]).copy()
    valid_df = valid_df[valid_df[target_column] > 0].reset_index(drop=True)

    if len(valid_df) < k:
        return AnalogyEstimateReport(
            status="INSUFFICIENT_ANALOGIES",
            target=target_column,
            target_unit=manifest.get("quality_summary", {}).get("unit", "units"),
            k_analogies=k,
            analogy_coverage_pct=0.0,
            mean_similarity_pct=0.0,
            point_estimate=None,
            low_estimate=None,
            high_estimate=None,
            similar_projects=[],
            notes=[f"Dataset has only {len(valid_df)} rows with valid target values, need at least k={k}."]
        )

    # Find common numeric features
    numeric_cols = [
        col for col in query_features
        if col in valid_df.columns and pd.api.types.is_numeric_dtype(valid_df[col])
    ]

    if not numeric_cols:
        return AnalogyEstimateReport(
            status="INSUFFICIENT_ANALOGIES",
            target=target_column,
            target_unit="units",
            k_analogies=k,
            analogy_coverage_pct=0.0,
            mean_similarity_pct=0.0,
            point_estimate=None,
            low_estimate=None,
            high_estimate=None,
            similar_projects=[],
            notes=["No matching numeric features between query and dataset."]
        )

    # Standardize features
    scaler = StandardScaler()
    X_hist = valid_df[numeric_cols].fillna(valid_df[numeric_cols].median()).values
    X_hist_scaled = scaler.fit_transform(X_hist)

    q_vals = np.array([[query_features[col] for col in numeric_cols]])
    q_scaled = scaler.transform(q_vals)

    # Compute Euclidean distances
    dists = np.linalg.norm(X_hist_scaled - q_scaled, axis=1)

    # Sort nearest
    nearest_indices = np.argsort(dists)[:k]
    max_possible_dist = np.sqrt(len(numeric_cols) * 4.0)  # ~2 std deviations per feature

    similar_projects: List[SimilarProject] = []
    similarities: List[float] = []

    for idx in nearest_indices:
        d = float(dists[idx])
        sim = max(0.0, min(100.0, round((1.0 - (d / max(max_possible_dist, 1e-6))) * 100.0, 1)))
        similarities.append(sim)

        row_dict = valid_df.iloc[idx][numeric_cols].to_dict()
        actual_val = float(valid_df.iloc[idx][target_column])

        similar_projects.append(SimilarProject(
            project_index=int(idx),
            similarity_score_pct=sim,
            distance=round(d, 3),
            actual_target_value=round(actual_val, 2),
            target_unit="units",
            features=row_dict
        ))

    mean_sim = float(np.mean(similarities))

    if mean_sim < min_similarity_threshold:
        return AnalogyEstimateReport(
            status="INSUFFICIENT_ANALOGIES",
            target=target_column,
            target_unit="units",
            k_analogies=k,
            analogy_coverage_pct=round(len(numeric_cols) / max(len(query_features), 1) * 100, 1),
            mean_similarity_pct=round(mean_sim, 1),
            point_estimate=None,
            low_estimate=None,
            high_estimate=None,
            similar_projects=similar_projects,
            notes=[f"Nearest analogies have average similarity {mean_sim:.1f}% which is below confidence threshold ({min_similarity_threshold}%). Refusing to invent estimate."]
        )

    # Weighted average by similarity
    weights = np.array(similarities) / max(sum(similarities), 1e-9)
    target_vals = np.array([p.actual_target_value for p in similar_projects])

    est_point = float(np.sum(weights * target_vals))
    low_est = float(np.min(target_vals))
    high_est = float(np.max(target_vals))

    return AnalogyEstimateReport(
        status="SUCCESS",
        target=target_column,
        target_unit="units",
        k_analogies=k,
        analogy_coverage_pct=round(len(numeric_cols) / max(len(query_features), 1) * 100, 1),
        mean_similarity_pct=round(mean_sim, 1),
        point_estimate=round(est_point, 2),
        low_estimate=round(low_est, 2),
        high_estimate=round(high_est, 2),
        similar_projects=similar_projects,
        notes=[
            f"Successfully derived from {k} most similar historical projects in {dataset_id}.",
            f"Feature coverage: {len(numeric_cols)} numeric attributes evaluated."
        ]
    )
