"""Tests for the KLE Fest 2 / Estimo integrated estimate output pipeline."""

import importlib.util
import json
import sys
from pathlib import Path

from backend.app.core.config import settings


PIPELINE_PATH = settings.base_dir / "KLE fest 2" / "pipeline_app" / "app.py"
PIPELINE_SPEC = importlib.util.spec_from_file_location("kle_pipeline_test_module", PIPELINE_PATH)
assert PIPELINE_SPEC is not None and PIPELINE_SPEC.loader is not None
pipeline = importlib.util.module_from_spec(PIPELINE_SPEC)
sys.modules[PIPELINE_SPEC.name] = pipeline
PIPELINE_SPEC.loader.exec_module(pipeline)


def test_pipeline_displays_and_persists_each_provider_output(monkeypatch, tmp_path):
    raw_gemini = '{"hardware_requirement":[],"software_requirement":{"project_name":"Output test"}}'
    raw_prediction = {
        "target": "Effort",
        "status": "ML_PREDICTION",
        "model_file_path": str(settings.models_dir / "Effort" / "v-test" / "model.joblib"),
        "prediction": 123.45,
    }
    raw_nemotron = "Hardware and software estimate summary."
    gemini_output = {
        "hardware_requirement": [],
        "software_requirement": {"project_name": "Output test", "labor_items": []},
    }

    directories = {
        "GEMINI_RESPONSES_DIR": tmp_path / "gemini_responses",
        "MODEL_PREDICTIONS_DIR": tmp_path / "model_predictions",
        "NEMOTRON_RESPONSES_DIR": tmp_path / "nemotron_responses",
    }
    for name, directory in directories.items():
        directory.mkdir()
        monkeypatch.setattr(pipeline, name, directory)

    monkeypatch.setattr(
        pipeline,
        "_run_gemini_agent_with_raw_response",
        lambda **kwargs: (gemini_output, raw_gemini, "gemini", raw_gemini),
    )
    monkeypatch.setattr(
        pipeline,
        "run_hardware_agent",
        lambda items: {"items": [], "total": {"min": 0, "likely": 0, "max": 0}},
    )
    monkeypatch.setattr(
        pipeline,
        "run_software_agent_and_model",
        lambda payload: {
            "raw_model_prediction": raw_prediction,
            "ml_prediction": raw_prediction,
            "total": {"min": 0, "likely": 0, "max": 0},
        },
    )
    monkeypatch.setattr(pipeline, "_call_nemotron", lambda prompt: raw_nemotron)
    monkeypatch.setattr(
        pipeline,
        "run_final_prediction",
        lambda *args: {"total_cost_inr": {"likely": 0}},
    )

    stream = list(pipeline.pipeline_generator("text", "Output test", "", "capture-test"))
    events = [
        json.loads(line[5:])
        for chunk in stream
        for line in chunk.splitlines()
        if line.startswith("data:")
    ]
    stage_outputs = {event.get("stage"): event for event in events if "stage" in event}

    assert stage_outputs["gemini"]["raw_output"] == raw_gemini
    assert stage_outputs["software"]["raw_output"] == json.dumps(
        raw_prediction, indent=2, ensure_ascii=False
    )
    assert stage_outputs["nemotron"]["data"]["response"] == raw_nemotron

    assert (directories["GEMINI_RESPONSES_DIR"] / "latest_gemini_response.txt").read_bytes() == raw_gemini.encode()
    assert json.loads(
        (directories["MODEL_PREDICTIONS_DIR"] / "latest_local_model_prediction.json").read_text(
            encoding="utf-8"
        )
    ) == raw_prediction
    assert (directories["NEMOTRON_RESPONSES_DIR"] / "latest_nemotron_response.txt").read_bytes() == raw_nemotron.encode()
