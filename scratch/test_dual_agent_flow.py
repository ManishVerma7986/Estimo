import sys
import json
from pathlib import Path

# Add paths
KLE_ROOT = Path(r"A:\PYTHON PROJECT\estimo 3.0\cost_estimation_ai\KLE fest 2")
REPO_ROOT = Path(r"A:\PYTHON PROJECT\estimo 3.0\cost_estimation_ai")

sys.path.insert(0, str(KLE_ROOT / "Hardware agent"))
sys.path.insert(0, str(REPO_ROOT))

import app as hw_agent
from backend.app.services.estimation import EstimationRequest, generate_full_estimate

# Test data from previous step
hw_items = [
    {
        "name": "Flight Controller Unit (FCU)",
        "spec": "Cube Orange+ or Pixhawk 6X",
        "suggested_models": [{"maker": "Holybro", "model": "Pixhawk 6X", "why": "Flight stability"}]
    },
    {
        "name": "Multispectral Camera",
        "spec": "5-band agricultural sensor",
        "suggested_models": [{"maker": "Micasense", "model": "RedEdge-P", "why": "NDVI crop index"}]
    }
]

sw_req = {
    "project_name": "Autonomous Drone for Agricultural Field Monitoring",
    "currency": "INR",
    "bom_items": [
        {"item_name": "Drone Fleet Cloud Management License", "quantity": 1, "unit_price": 45000.0, "unit": "license", "category": "software", "currency": "INR"}
    ],
    "labor_items": [
        {"role_name": "Lead Autonomous Systems Engineer", "hourly_rate": 1800.0, "hours": 120.0, "personnel_count": 1, "currency": "INR"},
        {"role_name": "Computer Vision & Edge AI Engineer", "hourly_rate": 1400.0, "hours": 160.0, "personnel_count": 1, "currency": "INR"},
        {"role_name": "Firmware & Drone Avionics Developer", "hourly_rate": 1200.0, "hours": 180.0, "personnel_count": 1, "currency": "INR"}
    ],
    "rules": {
        "overhead_percentage": 15.0,
        "contingency_percentage": 10.0,
        "tax_percentage": 18.0,
        "currency": "INR"
    },
    "ml_features": {
        "TeamExp": 4,
        "ManagerExp": 5,
        "Length": 8,
        "Transactions": 180,
        "Entities": 60,
        "PointsAjust": 250
    },
    "target_metric": "Effort",
    "analogy_dataset_id": "desharnais_software_projects_38c5d000"
}

print("Running Hardware Agent search for first item...")
hw_res = hw_agent.search_item("Pixhawk 6X flight controller")
print("HW best offer:", hw_res.get("best_offer"))
print("HW price summary:", hw_res.get("price_summary"))

print("\nRunning Local Model Estimation...")
est_req = EstimationRequest(**sw_req)
sw_estimate = generate_full_estimate(est_req)
print("Baseline dev cost:", sw_estimate.baseline_estimate.total_project_cost)
print("Monte Carlo P10 / P50 / P90:", sw_estimate.monte_carlo_uncertainty.p10, sw_estimate.monte_carlo_uncertainty.simulated_median_p50, sw_estimate.monte_carlo_uncertainty.p90)
print("ML Effort Prediction:", sw_estimate.ml_prediction.get("prediction"), "hours")
print("Analogy Estimate:", sw_estimate.analogy_estimate.point_estimate if sw_estimate.analogy_estimate else None)
