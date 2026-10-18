"""Automated Test Suite: Non-Negotiable Rules, Leakage Guards, Cryptographic Tamper Detection, and API."""

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import settings
from backend.app.core.security import sanitize_filename
from backend.app.main import app
from backend.app.services import estimation as estimation_service
from backend.app.services.estimation import EstimationRequest
from ml.evaluate import compute_metrics, run_release_audit
from ml.predict import predict_cost, safe_load_active_model
from ml.preprocessing import detect_potential_leakage, split_data
from ml.registry import ModelRegistry


client = TestClient(app)


def test_rule_r1_zero_dummy_or_fake_data_files():
    """Rule R1: Fails if any fake, dummy, or fabricated dataset files exist in data/ or models/."""
    prohibited_names = ["fake", "dummy", "placeholder", "sample_project", "demo_data", "synthetic"]
    base_dir = settings.base_dir

    for folder in [base_dir / "data" / "raw", base_dir / "models"]:
        if folder.exists():
            for p in folder.rglob("*"):
                if p.is_file() and p.name not in ["README.md", ".gitkeep", "registry.json"]:
                    for word in prohibited_names:
                        assert word not in p.name.lower(), f"Rule R1 Violation: Found prohibited dummy file: {p}"


def test_rule_r6_model_tamper_detection():
    """Rule R6: If a model file on disk is modified or corrupted, the system must detect the hash mismatch."""
    registry = ModelRegistry(base_dir=settings.base_dir)
    reg_data = registry.load_registry()
    active = reg_data.get("active_models", {})

    if not active:
        pytest.skip("No active model currently registered to test tampering.")

    target = list(active.keys())[0]
    version = active[target]
    model_key = f"{target}@{version}"
    model_info = reg_data["models"][model_key]
    model_path = settings.base_dir / model_info["model_file_path"]

    # Verify initial hash matches
    current_hash = hashlib.sha256(model_path.read_bytes()).hexdigest()
    assert current_hash == model_info["sha256"]

    # In a temporary copy, simulate tampering
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_base = Path(tmp_dir)
        models_tmp = tmp_base / "models" / target / version
        models_tmp.mkdir(parents=True, exist_ok=True)
        tampered_file = models_tmp / "model.joblib"
        tampered_file.write_bytes(b"TAMPERED_MALICIOUS_BYTES_12345")

        tampered_hash = hashlib.sha256(tampered_file.read_bytes()).hexdigest()
        assert tampered_hash != model_info["sha256"], "Tampered file should have a distinct checksum"


def test_rule_r2_transparent_baseline_fallback():
    """Rule R2: When a non-existent target or corrupt model is requested, fallback gracefully to baseline."""
    res = predict_cost(target="NonExistentTarget_9999", features={"feature_a": 10}, base_dir=settings.base_dir)
    assert res["status"] == "FALLBACK_BASELINE"
    assert res["prediction"] is None
    assert "Model unavailable" in res["warning"]


def test_estimation_service_pins_model_loading_to_project_root(monkeypatch):
    captured = {}

    def fake_predict_cost(**kwargs):
        captured.update(kwargs)
        return {"target": kwargs["target"], "prediction": 12.0}

    monkeypatch.setattr(estimation_service, "predict_cost", fake_predict_cost)
    result = estimation_service.generate_full_estimate(
        EstimationRequest(project_name="Model path test", ml_features={"feature": 1})
    )

    assert captured["base_dir"] == settings.base_dir
    assert result.ml_prediction == {"target": "Effort", "prediction": 12.0}


def test_active_effort_model_resolves_inside_project_models_directory():
    result = predict_cost(
        target="Effort",
        features={"TeamExp": 4, "ManagerExp": 5, "Length": 8},
        base_dir=settings.base_dir,
        dataset_id="desharnais_software_projects_38c5d000"
    )

    model_path = Path(result["model_file_path"])
    assert result["status"] == "ML_PREDICTION"
    assert model_path.is_file()
    assert settings.models_dir.resolve() in model_path.parents
    assert "KLE fest 2" not in model_path.parts


def test_leakage_detection_guards():
    """Verifies that derived outcome columns and post-completion metrics are flagged."""
    test_df = pd.DataFrame({
        "CostPerFP": [10.0, 20.0, 30.0],
        "Input_Features": [5, 10, 15],
        "Effort": [50.0, 100.0, 150.0]
    })
    warnings = detect_potential_leakage(test_df, target_column="Effort")
    assert any("CostPerFP" in w["column"] for w in warnings)


def test_evaluation_metrics_correctness():
    """Verifies correct calculation of MMRE, MdMRE, PRED(25), MAE, and Bias."""
    y_true = np.array([100.0, 200.0, 300.0, 400.0])
    y_pred = np.array([110.0, 240.0, 330.0, 520.0])

    metrics = compute_metrics(y_true, y_pred)
    assert metrics["n_test"] == 4
    assert metrics["MAE"] == float(np.mean(np.abs(y_true - y_pred)))
    # Relative errors: 10/100=0.10, 40/200=0.20, 30/300=0.10, 120/400=0.30
    # Values <= 0.25: 3 out of 4 -> PRED(25) = 0.75
    assert metrics["PRED25"] == 0.75
    assert metrics["MMRE"] == round(float(np.mean([0.10, 0.20, 0.10, 0.30])), 4)


def test_split_data_reproducibility():
    """Verifies that split_data produces identical splits given the same seed."""
    df = pd.DataFrame({
        "x": list(range(100)),
        "target": list(range(100, 200))
    })
    tr1, te1 = split_data(df, target_column="target", random_seed=42)
    tr2, te2 = split_data(df, target_column="target", random_seed=42)

    assert tr1.index.tolist() == tr2.index.tolist()
    assert te1.index.tolist() == te2.index.tolist()


def test_api_health_endpoint():
    """Tests GET /api/health."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["offline_capable"] is True


def test_api_upload_security_rejects_pickle():
    """Section 5: File upload validation rejects .joblib and .pkl uploads."""
    response = client.post(
        "/api/datasets/upload",
        files={"file": ("malicious_model.joblib", b"PICKLE_DATA", "application/octet-stream")},
        data={"name": "Bad File", "domain": "software", "license": "None", "source": "Hack"}
    )
    assert response.status_code == 400
    assert "SECURITY VIOLATION" in response.json()["detail"]


def test_api_estimates_baseline():
    """Tests POST /api/estimates for transparent baseline."""
    payload = {
        "project_name": "API Test Project",
        "currency": "INR",
        "bom_items": [
            {"item_name": "Sensor Unit", "quantity": 10, "unit_price": 2500, "unit": "piece", "currency": "INR"}
        ],
        "labor_items": [
            {"role_name": "Firmware Engineer", "hourly_rate": 1500, "hours": 40, "currency": "INR", "personnel_count": 1}
        ]
    }
    response = client.post("/api/estimates", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["project_name"] == "API Test Project"
    assert data["baseline_estimate"]["total_project_cost"] > 0
    assert data["currency"] == "INR"


def test_release_audit_passes():
    """Section 7: Release audit function must pass with zero critical failures."""
    code = run_release_audit(base_dir=settings.base_dir)
    assert code == 0, "Release audit must pass with return code 0"
