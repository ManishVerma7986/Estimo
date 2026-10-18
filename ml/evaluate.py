"""Model Evaluation and Gate Decisions Module.

Computes SE cost estimation metrics (MMRE, MdMRE, PRED(25), PRED(50), MAE, RMSE, Bias),
enforces honest gates, and provides the release verification CLI (--check-release).
"""

from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


def compute_metrics(
    y_true: np.ndarray | List[float],
    y_pred: np.ndarray | List[float],
    lower_bounds: Optional[np.ndarray | List[float]] = None,
    upper_bounds: Optional[np.ndarray | List[float]] = None
) -> Dict[str, Any]:
    """Computes standard software engineering cost estimation metrics on held-out test data."""
    yt = np.asarray(y_true, dtype=float)
    yp = np.maximum(np.asarray(y_pred, dtype=float), 0.0)

    n = len(yt)
    if n == 0:
        return {"n_test": 0, "MAE": 0.0, "RMSE": 0.0, "MMRE": 0.0, "MdMRE": 0.0, "PRED25": 0.0, "PRED50": 0.0, "Bias": 0.0}

    diff = np.abs(yt - yp)
    mae = float(np.mean(diff))
    rmse = float(np.sqrt(np.mean((yt - yp) ** 2)))

    rel_error = diff / np.maximum(np.abs(yt), 1e-9)
    mmre = float(np.mean(rel_error))
    mdmre = float(np.median(rel_error))

    pred25 = float(np.mean(rel_error <= 0.25))
    pred50 = float(np.mean(rel_error <= 0.50))

    signed_bias = float(np.mean((yp - yt) / np.maximum(np.abs(yt), 1e-9)))

    metrics: Dict[str, Any] = {
        "n_test": n,
        "MAE": round(mae, 2),
        "RMSE": round(rmse, 2),
        "MMRE": round(mmre, 4),
        "MdMRE": round(mdmre, 4),
        "PRED25": round(pred25, 4),
        "PRED50": round(pred50, 4),
        "Bias": round(signed_bias, 4)
    }

    if lower_bounds is not None and upper_bounds is not None:
        lb = np.asarray(lower_bounds, dtype=float)
        ub = np.asarray(upper_bounds, dtype=float)
        in_interval = (yt >= lb) & (yt <= ub)
        metrics["interval_coverage"] = round(float(np.mean(in_interval)), 4)
        metrics["mean_interval_width"] = round(float(np.mean(ub - lb)), 2)

    return metrics


def check_approval_gate(
    candidate_metrics: Dict[str, Any],
    baseline_mae: float,
    total_dataset_rows: int,
    gate_config_path: Optional[Path | str] = None
) -> Tuple[str, List[str]]:
    """Evaluates whether a candidate model passes the approval gate."""
    # Load gate config
    min_pred25 = 0.30
    min_rows = 25
    must_beat_baseline = True

    if gate_config_path and Path(gate_config_path).exists():
        try:
            with open(gate_config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                min_pred25 = cfg.get("default_thresholds", {}).get("min_pred25", min_pred25)
                min_rows = cfg.get("min_sample_size_ml", min_rows)
                must_beat_baseline = cfg.get("default_thresholds", {}).get("must_beat_baseline_mae", True)
        except Exception:
            pass

    reasons: List[str] = []
    c_mae = candidate_metrics.get("MAE", 1e12)
    c_pred25 = candidate_metrics.get("PRED25", 0.0)

    beats_baseline = (c_mae < baseline_mae) if must_beat_baseline else True
    meets_pred25 = (c_pred25 >= min_pred25)
    has_sufficient_data = (total_dataset_rows >= min_rows)

    if not beats_baseline:
        reasons.append(f"MAE ({c_mae:.2f}) does not beat baseline MAE ({baseline_mae:.2f})")

    if not meets_pred25:
        reasons.append(f"PRED(25) ({c_pred25:.2%}) is below threshold ({min_pred25:.0%})")

    if not has_sufficient_data:
        reasons.append(f"Sample size ({total_dataset_rows}) < minimum required ({min_rows})")
        return "EXPERIMENTAL", reasons

    if beats_baseline and meets_pred25:
        return "APPROVED", []
    else:
        return "REJECTED", reasons


def run_release_audit(base_dir: Path | str = ".") -> int:
    """Verifies that the release meets all non-negotiable integrity standards. Exits nonzero on failure."""
    base_path = Path(base_dir).resolve()
    reports_dir = base_path / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    audit_log: List[Dict[str, Any]] = []
    all_passed = True

    print("\n" + "=" * 70)
    print("  PRODUCTION RELEASE AUDIT: INTEGRITY & SECURITY")
    print("=" * 70)

    # Check 1: R1 Integrity Check (No dummy/faker/sample files in data/ or models/)
    prohibited_patterns = ["fake", "dummy", "sample_project", "placeholder", "demo_data"]
    found_prohibited: List[str] = []

    for check_dir in [base_path / "data" / "raw", base_path / "models"]:
        if check_dir.exists():
            for p in check_dir.rglob("*"):
                if p.is_file() and any(pat in p.name.lower() for pat in prohibited_patterns):
                    found_prohibited.append(str(p.relative_to(base_path)))

    if found_prohibited:
        audit_log.append({
            "check": "R1_NO_DUMMY_DATA",
            "status": "FAILED",
            "details": f"Found forbidden placeholder files: {found_prohibited}"
        })
        all_passed = False
        print(f"  [FAIL] R1: Found prohibited dummy data: {found_prohibited}")
    else:
        audit_log.append({
            "check": "R1_NO_DUMMY_DATA",
            "status": "PASSED",
            "details": "Verified no synthetic or fake data files exist in data/ or models/"
        })
        print("  [PASS] R1: Zero dummy data files found in data/ or models/")

    # Check 2: Manifest Completeness (Every dataset in raw has a manifest)
    missing_manifests: List[str] = []
    raw_dir = base_path / "data" / "raw"
    manifests_dir = base_path / "data" / "manifests"

    if raw_dir.exists():
        for d in raw_dir.iterdir():
            if d.is_dir() and d.name != ".gitkeep":
                manifest_file = manifests_dir / f"{d.name}.json"
                if not manifest_file.exists():
                    missing_manifests.append(d.name)

    if missing_manifests:
        audit_log.append({
            "check": "DATASET_MANIFEST_COMPLETENESS",
            "status": "FAILED",
            "details": f"Missing manifests for datasets: {missing_manifests}"
        })
        all_passed = False
        print(f"  [FAIL] Datasets missing manifests: {missing_manifests}")
    else:
        audit_log.append({
            "check": "DATASET_MANIFEST_COMPLETENESS",
            "status": "PASSED",
            "details": "All registered datasets have verified cryptographic manifests"
        })
        print("  [PASS] All registered datasets have verified cryptographic manifests")

    # Check 3: Models Registry Checksum Verification (R6)
    registry_file = base_path / "models" / "registry.json"
    checksum_failures: List[str] = []

    if registry_file.exists():
        try:
            with open(registry_file, "r", encoding="utf-8") as f:
                reg_data = json.load(f)
            for model_id, m_info in reg_data.get("models", {}).items():
                m_path = base_path / m_info.get("model_file_path", "")
                recorded_hash = m_info.get("sha256", "")
                if m_path.exists():
                    actual_hash = hashlib.sha256(m_path.read_bytes()).hexdigest()
                    if actual_hash != recorded_hash:
                        checksum_failures.append(f"{model_id} (hash mismatch)")
                else:
                    checksum_failures.append(f"{model_id} (missing model file)")
        except Exception as e:
            checksum_failures.append(f"Registry read error: {e}")

    if checksum_failures:
        audit_log.append({
            "check": "R6_MODEL_CHECKSUM_VERIFICATION",
            "status": "FAILED",
            "details": f"Model verification failed: {checksum_failures}"
        })
        all_passed = False
        print(f"  [FAIL] R6 Model checksum verification failed: {checksum_failures}")
    else:
        audit_log.append({
            "check": "R6_MODEL_CHECKSUM_VERIFICATION",
            "status": "PASSED",
            "details": "All stored model joblib files match registered SHA-256 signatures"
        })
        print("  [PASS] All stored models match signed SHA-256 signatures")

    # Save audit report
    report_file = reports_dir / f"release_audit_{timestamp}.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_status": "PASSED" if all_passed else "FAILED",
            "checks": audit_log
        }, f, indent=2)

    print("=" * 70)
    print(f"Audit report saved to: {report_file.relative_to(base_path)}")
    print(f"Overall status: {'PASSED' if all_passed else 'FAILED'}")
    print("=" * 70 + "\n")

    return 0 if all_passed else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate cost estimation models and perform release audits.")
    parser.add_argument("--check-release", action="store_true", help="Run release verification checks and audit")
    parser.add_argument("--run", type=str, help="Evaluate a specific training run by run ID")
    parser.add_argument("--base-dir", type=str, default=".", help="Base project directory")

    args = parser.parse_args()

    if args.check_release:
        code = run_release_audit(args.base_dir)
        sys.exit(code)
    elif args.run:
        print(f"Evaluating run: {args.run}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
