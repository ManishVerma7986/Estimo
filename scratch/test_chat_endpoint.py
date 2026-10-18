import json
import sys
from pathlib import Path

# Force UTF-8 stdout
if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path("KLE fest 2/pipeline_app").resolve()))
sys.path.insert(0, str(Path("KLE fest 2/Nvidea").resolve()))
import app

results_file = Path("scratch/final_stream_result.json")
stream_data = json.loads(results_file.read_text(encoding="utf-8"))
session_id = stream_data.get("session_id", "4dfbb6f43f1f309a")

app._chat_cache[session_id] = {
    "gemini": stream_data.get("gemini", {}),
    "hardware": stream_data.get("hardware", {}),
    "software": stream_data.get("software", {}),
    "prediction": stream_data.get("prediction", {})
}

client = app.app.test_client()
response = client.post("/api/chat", json={
    "session_id": session_id,
    "message": "Where is the STM32 development board sourced from, what is its price, and what is the offline ML model predicted effort for software?"
})

print(f"Status Code: {response.status_code}")
data = response.get_json()
print("Chatbot Reply:\n" + data.get("reply", ""))
