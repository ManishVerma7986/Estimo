-- database/schema.sql

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_text TEXT,
    input_type TEXT, -- 'text', 'image', or 'image+text'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS estimates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER,
    
    -- Final Cost Prediction (INR)
    total_cost_optimistic REAL,
    total_cost_likely REAL,
    total_cost_pessimistic REAL,
    
    -- Cost Breakdown (INR)
    hardware_cost_min REAL,
    hardware_cost_max REAL,
    software_dev_cost_min REAL,
    software_dev_cost_max REAL,
    licence_cost_min REAL,
    licence_cost_max REAL,
    
    -- Timeline (Months)
    effort_months_low REAL,
    effort_months_likely REAL,
    effort_months_high REAL,
    
    -- Metadata
    confidence TEXT,
    summary TEXT,
    
    -- Complex nested JSON data
    hw_items_json TEXT,   
    sw_items_json TEXT,   
    team_json TEXT,       
    sources_json TEXT,    
    
    -- NEW: Decision Support & Accuracy Tracking (Estimate vs Actual)
    actual_cost REAL,               -- Filled in after project completion
    actual_effort_months REAL,      -- Filled in after project completion
    estimate_accuracy REAL,         -- Calculated as 1 - (|actual - predicted| / actual)
    project_status TEXT DEFAULT 'predicted', -- 'predicted' or 'completed'
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS okf_rates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role_name TEXT,
    rate_per_hour REAL,
    source_url TEXT,
    date_fetched DATE
);