-- database/schema.sql


-- 1. Stores the initial project input

CREATE TABLE IF NOT EXISTS projects
(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);



-- 2. Stores the output from the models and cost engine
CREATE TABLE IF NOT EXISTS estimates
(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER,
    decomposed_tasks TEXT,
    effort_score REAL,
    range_p50 REAL,
    range_p80 REAL,
    total_cost REAL,
    shap_drivers TEXT,
    cost_breakdown TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);



-- 3. Stores the rates fetched by the web search agent
CREATE TABLE IF NOT EXISTS okf_rates
(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role_name TEXT,
    rate_per_hour REAL,
    source_url TEXT,
    date_fetched DATE
);

