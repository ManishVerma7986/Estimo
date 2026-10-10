# database/seed_data.py
import json
import os
import sqlite3


def create_mock_data():
    db_path = os.path.join(os.path.dirname(__file__), "cost_estimator.db")
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    with open(schema_path, "r") as f:
        cursor.executescript(f.read())

    cursor.execute("DELETE FROM estimates")
    cursor.execute("DELETE FROM projects")

    # Mock Data mimicking Team 1's actual output
    mock_projects = [
        {
            "text": "Build an Automated Smart Irrigation System",
            "type": "image+text",
            "optimistic": 76800,
            "likely": 108800,
            "pessimistic": 140800,
            "hw_min": 4800,
            "hw_max": 8800,
            "dev_min": 72000,
            "dev_max": 132000,
            "lic_min": 0,
            "lic_max": 0,
            "months_low": 1.5,
            "months_likely": 2.0,
            "months_high": 3.0,
            "confidence": "HIGH",
            "summary": "This cost estimate covers the hardware procurement for an IoT-based automated irrigation system.",
            "hw_items": [
                {
                    "name": "Water Solenoid Valve",
                    "price_summary": {"min": 500, "max": 800},
                }
            ],
            "sw_items": [],
            "team": [
                {
                    "role": "Embedded Firmware Engineer",
                    "reason": "Develops ESP32 C++ code",
                }
            ],
            "sources": ["https://example.com/valve"],
        }
    ]

    for proj in mock_projects:
        cursor.execute(
            "INSERT INTO projects (project_text, input_type) VALUES (?, ?)",
            (proj["text"], proj["type"]),
        )
        project_id = cursor.lastrowid

        cursor.execute(
            """
            INSERT INTO estimates (
                project_id, total_cost_optimistic, total_cost_likely, total_cost_pessimistic,
                hardware_cost_min, hardware_cost_max, software_dev_cost_min, software_dev_cost_max,
                licence_cost_min, licence_cost_max, effort_months_low, effort_months_likely,
                effort_months_high, confidence, summary, hw_items_json, sw_items_json, team_json, sources_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                project_id,
                proj["optimistic"],
                proj["likely"],
                proj["pessimistic"],
                proj["hw_min"],
                proj["hw_max"],
                proj["dev_min"],
                proj["dev_max"],
                proj["lic_min"],
                proj["lic_max"],
                proj["months_low"],
                proj["months_likely"],
                proj["months_high"],
                proj["confidence"],
                proj["summary"],
                json.dumps(proj["hw_items"]),
                json.dumps(proj["sw_items"]),
                json.dumps(proj["team"]),
                json.dumps(proj["sources"]),
            ),
        )

    conn.commit()
    conn.close()
    print(f"Success! Mock database created at {db_path}")


if __name__ == "__main__":
    create_mock_data()
