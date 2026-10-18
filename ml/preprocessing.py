"""Preprocessing, Leakage Detection, and Data Splitting Module.

Ensures that transformers are fitted exclusively on the training split, prevents target leakage,
and structures feature pipelines for numeric and categorical attributes.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

KNOWN_LEAKAGE_SUBSTRINGS = [
    "costper", "cfp", "p20", "lneff", "lnsize", "n_effort", "actual_des"
]

KNOWN_POST_COMPLETION_TERMS = [
    "actual_time", "actual.duration", "completion_date", "finish_date"
]


def detect_potential_leakage(
    df: pd.DataFrame,
    target_column: str,
    correlation_threshold: float = 0.98
) -> List[Dict[str, Any]]:
    """Flags features that appear to be derived from the target or post-completion outcomes."""
    warnings: List[Dict[str, Any]] = []
    target_lower = target_column.lower()

    if target_column not in df.columns:
        return warnings

    y_series = pd.to_numeric(df[target_column], errors="coerce")

    for col in df.columns:
        if col == target_column:
            continue
        col_lower = col.lower()

        # Check keyword matches
        if any(leak in col_lower for leak in KNOWN_LEAKAGE_SUBSTRINGS):
            warnings.append({
                "column": col,
                "reason": f"Column name contains known post-facto or derived outcome pattern",
                "severity": "CRITICAL"
            })
            continue

        # Check correlation
        if pd.api.types.is_numeric_dtype(df[col]):
            s = pd.to_numeric(df[col], errors="coerce")
            valid = s.notnull() & y_series.notnull()
            if valid.sum() > 5:
                corr = abs(float(s[valid].corr(y_series[valid])))
                if corr >= correlation_threshold:
                    warnings.append({
                        "column": col,
                        "correlation": round(corr, 4),
                        "reason": f"High absolute correlation ({corr:.2f}) with target suggests target leakage or duplicate column",
                        "severity": "HIGH"
                    })

    return warnings


def split_data(
    df: pd.DataFrame,
    target_column: str,
    split_strategy: str = "random",
    test_size: float = 0.20,
    time_column: Optional[str] = None,
    group_column: Optional[str] = None,
    random_seed: int = 42
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Splits dataset into train and test sets according to the chosen strategy."""
    n = len(df)
    if n < 5:
        raise ValueError(f"Dataset has only {n} rows, cannot create train/test split.")

    if split_strategy == "time" and time_column and time_column in df.columns:
        sorted_df = df.sort_values(by=time_column).reset_index(drop=True)
        cut = int(n * (1 - test_size))
        return sorted_df.iloc[:cut].copy(), sorted_df.iloc[cut:].copy()

    elif split_strategy == "group" and group_column and group_column in df.columns:
        unique_groups = df[group_column].dropna().unique()
        rng = np.random.RandomState(random_seed)
        rng.shuffle(unique_groups)
        n_test_groups = max(1, int(len(unique_groups) * test_size))
        test_groups = set(unique_groups[:n_test_groups])
        train_df = df[~df[group_column].isin(test_groups)].copy()
        test_df = df[df[group_column].isin(test_groups)].copy()
        return train_df, test_df

    else:
        # Default stratified/random holdout with fixed seed
        rng = np.random.RandomState(random_seed)
        indices = np.arange(n)
        rng.shuffle(indices)
        cut = int(n * (1 - test_size))
        return df.iloc[indices[:cut]].copy(), df.iloc[indices[cut:]].copy()


def build_preprocessor_pipeline(
    feature_types: Dict[str, str],
    target_column: str
) -> Tuple[ColumnTransformer, List[str], List[str]]:
    """Builds a scikit-learn ColumnTransformer from a schema mapping."""
    numeric_cols = [
        col for col, ftype in feature_types.items()
        if ftype == "numeric" and col != target_column
    ]
    categorical_cols = [
        col for col, ftype in feature_types.items()
        if ftype in ["categorical", "ordinal"] and col != target_column
    ]

    transformers = []
    if numeric_cols:
        num_pipeline = Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler())
        ])
        transformers.append(("numeric", num_pipeline, numeric_cols))

    if categorical_cols:
        cat_pipeline = Pipeline([
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False))
        ])
        transformers.append(("categorical", cat_pipeline, categorical_cols))

    column_transformer = ColumnTransformer(
        transformers=transformers,
        remainder="drop"
    )

    return column_transformer, numeric_cols, categorical_cols
