import sys
import json
from pathlib import Path

sys.path.insert(0, r"A:\PYTHON PROJECT\estimo 3.0\cost_estimation_ai\KLE fest 2\pipeline_app")
import app

client = app.app.test_client()

print("Sending POST request to /api/estimate with text input...")
resp = client.post("/api/estimate", data={
    "mode": "text",
    "text": "Smart Building Controller Prototype with STM32 microcontroller and temperature/humidity sensors"
})

print("Status code:", resp.status_code)
print("Content-Type:", resp.content_type)

events = []
done_data = None

for line in resp.response:
    decoded = line.decode("utf-8")
    for part in decoded.split("\n\n"):
        if not part.strip():
            continue
        ev = "message"
        data_lines = []
        for l in part.split("\n"):
            if l.startswith("event:"):
                ev = l.split(":", 1)[1].strip()
            elif l.startswith("data:"):
                data_lines.append(l.split(":", 1)[1].strip())
        if data_lines:
            try:
                parsed_data = json.loads("\n".join(data_lines))
                events.append((ev, parsed_data))
                if ev == "stage":
                    stage = parsed_data.get("stage")
                    status = parsed_data.get("status")
                    msg = parsed_data.get("message", "")
                    # Safe print
                    safe_msg = msg.encode("ascii", errors="replace").decode("ascii")
                    print(f"STAGE [{stage}] -> {status}: {safe_msg}")
                elif ev == "done":
                    done_data = parsed_data
                    print("DONE EVENT RECEIVED SUCCESSFULLY!")
            except Exception as e:
                print("Parse error on chunk:", e)

# Save final result to inspect
if done_data:
    out_file = Path(r"A:\PYTHON PROJECT\estimo 3.0\cost_estimation_ai\scratch\final_stream_result.json")
    out_file.write_text(json.dumps(done_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nFinal result successfully saved to {out_file}")
    print("HW items count:", len(done_data.get("hardware", {}).get("items", [])))
    print("HW total:", done_data.get("hardware", {}).get("total"))
    print("SW labor roles count:", len(done_data.get("software", {}).get("labor_breakdown", [])))
    print("SW baseline total:", done_data.get("software", {}).get("baseline_estimate", {}).get("total_project_cost"))
    print("SW Monte Carlo P50:", done_data.get("software", {}).get("monte_carlo_uncertainty", {}).get("simulated_median_p50"))
    print("SW ML predicted hours:", done_data.get("software", {}).get("ml_prediction", {}).get("prediction"))
    print("SW Analogies count:", len(done_data.get("software", {}).get("analogy_estimate", {}).get("similar_projects", [])))
    print("Final synthesis likely total:", done_data.get("prediction", {}).get("total_cost_inr", {}).get("likely"))
else:
    print("WARNING: No done event was emitted.")
