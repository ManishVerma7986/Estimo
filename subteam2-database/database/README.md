# Subteam 2 Database Schema

This folder contains the database schema and mock data for the Cost Estimation Engine.


# Database Schema

```mermaid
erDiagram
    PROJECTS ||--o{ ESTIMATES : "generates"
    
    PROJECTS {
        int id PK
        string project_text
        timestamp created_at
    }

    ESTIMATES {
        int id PK
        int project_id FK
        string decomposed_tasks "JSON"
        float effort_score
        float range_p50
        float range_p80
        float total_cost
        string shap_drivers "JSON"
        string cost_breakdown "JSON"
    }

    OKF_RATES {
        int id PK
        string role_name
        float rate_per_hour
        string source_url
        date date_fetched
    }
