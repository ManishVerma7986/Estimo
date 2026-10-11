# database/update_actuals.py
import os
import sqlite3


def update_project_actuals(project_id, actual_cost, actual_effort_months):
    """
    Updates the database when a project is completed, enabling MMRE calculation
    and future Analogy-Based Estimation (ABE).
    """
    db_path = os.path.join(os.path.dirname(__file__), "cost_estimator.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Fetch the predicted values
    cursor.execute(
        "SELECT total_cost_likely, effort_months_likely FROM estimates WHERE project_id = ?",
        (project_id,),
    )
    result = cursor.fetchone()

    if not result:
        print(f"Error: Project ID {project_id} not found.")
        conn.close()
        return

    predicted_cost, predicted_effort = result

    # Calculate Accuracy (1 - |Actual - Predicted| / Actual)
    if actual_cost and predicted_cost:
        accuracy = 1 - (abs(actual_cost - predicted_cost) / actual_cost)
    else:
        accuracy = 0.0

    # Update the record
    cursor.execute(
        """
        UPDATE estimates 
        SET actual_cost = ?, actual_effort_months = ?, estimate_accuracy = ?, project_status = 'completed'
        WHERE project_id = ?
    """,
        (actual_cost, actual_effort_months, accuracy, project_id),
    )

    conn.commit()
    conn.close()
    print(f"Project {project_id} updated successfully. Accuracy: {accuracy * 100:.2f}%")


if __name__ == "__main__":
    # Example: Updating Project 1 with its actual completion data
    update_project_actuals(project_id=1, actual_cost=115000, actual_effort_months=2.1)
