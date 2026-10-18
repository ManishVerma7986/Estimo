import json
from pathlib import Path
import time

repo_root = Path(__file__).resolve().parent.parent
outer_root = repo_root.parent

dirs = [
    repo_root / "gemini_responses",
    repo_root / "model_predictions",
    outer_root / "gemini_responses",
    outer_root / "model_predictions",
]

for d in dirs:
    d.mkdir(exist_ok=True)
    print(f"Directory ensured: {d}")

# Load previous run result
res_file = repo_root / "scratch" / "final_stream_result.json"
if res_file.exists():
    data = json.loads(res_file.read_text(encoding="utf-8"))
    session_id = data.get("session_id", "4dfbb6f43f1f309a")
    gemini_out = data.get("gemini", {})
    sw_out = data.get("software", {})
    hw_out = data.get("hardware", {})
    prediction = data.get("prediction", {})

    ts = time.strftime("%Y%m%d_%H%M%S")
    
    pred_payload = {
        "session_id": session_id,
        "timestamp": ts,
        "software_development_estimate": sw_out,
        "unified_prediction_summary": prediction,
        "hardware_estimate": hw_out
    }

    # Save to repo root directories
    for target_gemini, target_pred in [
        (repo_root / "gemini_responses", repo_root / "model_predictions"),
        (outer_root / "gemini_responses", outer_root / "model_predictions")
    ]:
        (target_gemini / f"gemini_response_{session_id}.json").write_text(
            json.dumps(gemini_out, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (target_gemini / "latest_gemini_response.json").write_text(
            json.dumps(gemini_out, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (target_pred / f"model_prediction_{session_id}.json").write_text(
            json.dumps(pred_payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (target_pred / "latest_model_prediction.json").write_text(
            json.dumps(pred_payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"Saved initial outputs to {target_gemini} and {target_pred}")

print("Done!")
