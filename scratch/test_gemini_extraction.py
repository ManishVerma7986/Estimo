import sys
import json
from pathlib import Path

sys.path.insert(0, r"A:\PYTHON PROJECT\estimo 3.0\cost_estimation_ai\KLE fest 2\Nvidea")
import image as _img
import json_repair

client = _img._client()
desc = "Autonomous Drone for Agricultural Field Monitoring with Multispectral Camera and AI Disease Detection"

prompt = f"""You are a senior Systems Architect and Chief Technology Officer.
A client wants to develop: "{desc}"

Generate TWO distinct, high-fidelity JSON outputs:
1. "hardware_requirement":
   List 4-8 physical hardware products, microcontrollers, sensors, motors, peripherals needed.
   For each item: "name", "spec", "quantity", and "suggested_models" (array of {{"maker": "...", "model": "...", "why": "..."}}).

2. "software_requirement":
   Full scope engineering payload:
   - "project_name": "{desc}"
   - "currency": "INR"
   - "bom_items": 1-3 software tools / cloud licenses (item_name, quantity, unit_price, unit, category, currency, source, region)
   - "labor_items": 3-5 software/firmware/systems roles (role_name, hourly_rate in INR, hours, personnel_count, currency)
   - "rules": {{"overhead_percentage": 15.0, "contingency_percentage": 10.0, "tax_percentage": 18.0, "currency": "INR"}}
   - "ml_features": {{"TeamExp": 4, "ManagerExp": 5, "Length": 8, "Transactions": 200, "Entities": 75, "PointsAjust": 280}}
   - "target_metric": "Effort"
   - "analogy_dataset_id": "desharnais_software_projects_38c5d000"

Return compact valid JSON only:
"""

resp = client.models.generate_content(model=_img.MODEL, contents=prompt)
raw = resp.text
parsed = json_repair.repair_json(raw, return_objects=True)
print("Keys:", list(parsed.keys()))
print("Hardware count:", len(parsed.get("hardware_requirement", [])))
print("First HW item:", parsed.get("hardware_requirement", [])[0] if parsed.get("hardware_requirement") else None)
print("Software requirement project_name:", parsed.get("software_requirement", {}).get("project_name"))
print("Software labor items count:", len(parsed.get("software_requirement", {}).get("labor_items", [])))
