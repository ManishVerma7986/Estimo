# database/seed_data.py
import sqlite3
import json
import os


def create_mock_data():
    # Ensure we are in the right directory
    db_path = os.path.join(os.path.dirname(__file__), "cost_estimator.db")
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Read and execute the schema
    with open(schema_path, "r") as f:
        cursor.executescript(f.read())

    # Clean up existing data to prevent duplicates on multiple runs
    cursor.execute("DELETE FROM estimates")
    cursor.execute("DELETE FROM projects")
    cursor.execute("DELETE FROM okf_rates")

    # Insert Mock Projects and Estimates
    mock_projects = [
        (
            "Build a data pipeline in AWS using Airflow and Snowflake",
            45.5,
            40.0,
            50.0,
            5500.0,
            json.dumps({"cloud_cost": 0.4, "dev_time": 0.6}),
            json.dumps({"dev": 3500, "cloud": 2000}),
        ),
        (
            "Migrate legacy on-premise database to Azure SQL",
            80.0,
            75.0,
            90.0,
            12000.0,
            json.dumps({"migration_complexity": 0.7, "downtime_risk": 0.3}),
            json.dumps({"dev": 8000, "cloud": 4000}),
        ),
        (
            "Develop a mobile app backend with Node.js and MongoDB",
            60.0,
            55.0,
            70.0,
            8500.0,
            json.dumps({"api_complexity": 0.5, "security_risk": 0.5}),
            json.dumps({"dev": 6500, "db": 2000}),
        ),
    ]

    for proj in mock_projects:
        cursor.execute("INSERT INTO projects (project_text) VALUES (?)", (proj[0],))
        project_id = cursor.lastrowid
        cursor.execute(
            """
            INSERT INTO estimates (project_id, effort_score, range_p50, range_p80, total_cost, shap_drivers, cost_breakdown)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (project_id, proj[1], proj[2], proj[3], proj[4], proj[5], proj[6]),
        )

    # Insert Mock OKF Rates
    rates = [
        ("Data Engineer", 85.00, "https://okf.example.com/data-eng", "2026-10-10"),
        ("Cloud Architect", 120.00, "https://okf.example.com/cloud-arch", "2026-10-10"),
        ("Frontend Developer", 75.00, "https://okf.example.com/fe-dev", "2026-10-10"),
    ]
    cursor.executemany(
        "INSERT INTO okf_rates (role_name, rate_per_hour, source_url, date_fetched) VALUES (?, ?, ?, ?)",
        rates,
    )

    conn.commit()
    conn.close()
    print(f"Success! Mock database created at {db_path}")


if __name__ == "__main__":
    create_mock_data()
