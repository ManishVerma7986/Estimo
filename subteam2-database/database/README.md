# Subteam 2 Database Schema

This folder contains the database schema and mock data for the Cost Estimation Engine.


# Database Schema

```mermaid
erDiagram
    PROJECTS ||--o{ ESTIMATES : "generates"
    
    PROJECTS {
        int id PK
        string project_text
        string input_type "text, image, or image+text"
        timestamp created_at
    }

    ESTIMATES {
        int id PK
        int project_id FK
        
        float total_cost_optimistic
        float total_cost_likely
        float total_cost_pessimistic
        
        float hardware_cost_min
        float hardware_cost_max
        float software_dev_cost_min
        float software_dev_cost_max
        float licence_cost_min
        float licence_cost_max
        
        float effort_months_low
        float effort_months_likely
        float effort_months_high
        
        string confidence
        string summary
        
        string hw_items_json "JSON"
        string sw_items_json "JSON"
        string team_json "JSON"
        string sources_json "JSON"
        timestamp created_at
    }

    OKF_RATES {
        int id PK
        string role_name
        float rate_per_hour
        string source_url
        date date_fetched
    }