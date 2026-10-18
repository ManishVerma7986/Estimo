# Estimo 3.0 — User & Operational Guide

## Overview
Estimo 3.0 is a production-quality, offline-capable application for estimating total development costs and effort across personnel, materials, equipment, software licenses, infrastructure, timeline, overheads, and taxes.

---

## 1. Quickstart & Local Setup

### Prerequisites
- Python 3.12+ (Python 3.14 compatible)
- Node.js 18+ & npm

### Starting the Backend
```powershell
cd "a:\PYTHON PROJECT\estimo 3.0\cost_estimation_ai"
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```
The API is available at `http://127.0.0.1:8000` with interactive Swagger docs at `http://127.0.0.1:8000/docs`.

### Starting the Frontend
```powershell
cd "a:\PYTHON PROJECT\estimo 3.0\cost_estimation_ai\frontend"
npm.cmd run dev
```
Open `http://localhost:3000` in your web browser.

---

## 2. CLI Operations

### Ingesting Datasets
```powershell
python -m ml.data_ingestion --file "dataset/Desharnais.csv" --name "Desharnais Projects" --domain "software" --license "PROMISE Repository Research Use" --source "http://promise.site.uottawa.ca/SERepository"
```

### Training Models
```powershell
python -m ml.train --dataset desharnais_projects_<hash> --target Effort --split random
```

### Running Model Governance & Version Control
```powershell
# List registered models
python -m ml.registry list

# Verify all disk model checksums
python -m ml.registry verify

# Activate a specific version
python -m ml.registry activate Effort <version>

# Roll back to the previous version
python -m ml.registry rollback Effort
```

### Running Inference
```powershell
python -m ml.predict --target Effort --json '{"TeamExp": 3, "ManagerExp": 4, "Length": 12, "Transactions": 200, "Entities": 80, "PointsAjust": 280}'
```

### Production Release Audit Check
```powershell
python -m ml.evaluate --check-release
```
Exits with code 0 if all non-negotiable integrity standards (R1 zero dummy data, R6 valid checksums, manifest completeness) pass.

---

## 3. Core Engine Mechanics

### Transparent Baseline (Section 3.1)
- Computed from BOM items ($quantity \times unit\_price$) and labor roles ($hours \times hourly\_rate \times personnel$).
- Overheads, contingency buffers, and taxes are applied as configurable multipliers.
- Prices and rates come strictly from user inputs. Missing prices trigger validation errors.

### Analogy Estimator (Section 3.2)
- Locates the $k$ nearest historical projects in imported user datasets using standardized Euclidean distance.
- Refuses to predict if mean similarity falls below confidence threshold ($40\%$).

### Uncertainty & Monte Carlo (Section 3.4)
- 2,000 deterministic simulation iterations using a fixed random seed.
- Computes P10, P50 (expected), and P90 ranges.
- Ranks variables by variance contribution to identify cost drivers.

### What-If Scenarios (Section 3.6)
- Evaluates cost deltas and percentage changes for labor shocks, material price inflation, and risk contingency adjustments.
