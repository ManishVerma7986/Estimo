# Estimo 3.0 — AI Cost & Effort Estimation Application

Production-quality, offline-capable AI application that estimates the total development cost and effort of engineering and building-product projects (personnel, materials, equipment, software licenses, infrastructure, timeline, overheads, and taxes).

---

## 1. Non-Negotiable Integrity Rules Compliance

| Rule | Enforcement Mechanism |
|------|------------------------|
| **R1. NO DUMMY DATA** | Starts in an honest empty state (`"No dataset loaded. Import a dataset to begin."`). Zero faker or synthetic rows. All 13 bundled benchmarks come from the PROMISE Software Engineering Repository. |
| **R2. NO FABRICATED RESULTS** | All outputs are computed strictly from real data or real model runs. Missing or corrupt models gracefully fall back to the transparent baseline calculator. |
| **R3. LOCAL MODEL PERSISTENCE** | Approved models are versioned on disk in `models/<target>/<version>/` and loaded at startup. Predictions never trigger retraining. |
| **R4. USER-TRAINABLE** | Full Bring-Your-Own-Dataset workflow via web UI and CLI (`python -m ml.train`). |
| **R5. HONEST EVALUATION** | Metrics (MMRE, MdMRE, PRED(25), MAE, RMSE, Bias) computed strictly on held-out test splits. Models with $n < 25$ are labelled EXPERIMENTAL. |
| **R6. SAFE DESERIALIZATION** | All `.joblib` model artifacts are verified against signed SHA-256 checksums in `models/registry.json`. Arbitrary model uploads are blocked. |
| **R7. CONFIGURABLE CURRENCY** | Default currency is `INR` (₹), fully configurable to `USD`, `EUR`, `GBP`. |

---

## 2. Real PROMISE Benchmarks & Evaluation Summary

Held-out evaluation metrics from `SE_Cost_Estimation_Training_Evaluation.ipynb`:

| Dataset | Usable Rows | Target Column | Best Model | Held-out MAE | Held-out MMRE | Held-out PRED(25) | Status |
|---------|-------------|---------------|------------|--------------|---------------|-------------------|--------|
| **UCP_Dataset** | 71 | `Real_Effort_Person_Hours` | GradientBoosting | 179.81 | 0.0254 | **100.0%** | APPROVED |
| **China** | 499 | `Effort` | XGBoost | 453.77 | 0.1006 | **96.0%** | APPROVED |
| **Kitchenham** | 145 | `Actual.effort` | RandomForest | 411.50 | 0.2138 | **82.8%** | APPROVED |
| **Finnish** | 38 | `dev.eff.hrs.` | GradientBoosting | 1088.79 | 0.4350 | **75.0%** | APPROVED |
| **Maxwell** | 62 | `Effort` | GradientBoosting | 2640.59 | 0.2672 | **69.2%** | APPROVED |
| **Miyazaki94** | 48 | `MM` | RandomForest | 21.06 | 0.2783 | **50.0%** | APPROVED |
| **Albrecht** | 24 | `Effort` | Ridge | 2.64 | 0.4046 | **50.0%** | EXPERIMENTAL ($n < 25$) |
| **Valdes-Souto** | 57 | `Effort` | XGBoost | 838.18 | 9.5237 | **50.0%** | APPROVED |
| **NASA93** | 93 | `act_effort` | DecisionTree | 167.29 | 0.3988 | **47.4%** | APPROVED |
| **Desharnais** | 81 | `Effort` | XGBoost | 2222.00 | 0.4753 | **35.3%** | APPROVED |
| **Subbiah** | 72 | `TotalLaborCost` | GradientBoosting | 4777.67 | 0.8178 | **26.7%** | REJECTED (PRED25 < 30%) |
| **COCOMO-81** | 63 | `actual` | Analogy k-NN | 462.75 | 4.4604 | **15.4%** | REJECTED (PRED25 < 30%) |

---

## 3. Quickstart & Verification

### Integrated KLE Fest 2 Workflow
Run `python app.py` from `KLE fest 2/pipeline_app/` to use the integrated text/image/PDF estimator. Gemini extracts both hardware requirements and the software full-scope payload; the KLE hardware agent prices products; Estimo's checked local model registry calculates software effort alongside baseline, Monte Carlo, and analogy results; Nemotron provides a separate narrative interpretation without changing numeric totals.

Each stage's response can be expanded in the frontend progress panel. Raw Gemini, local model prediction, and Nemotron outputs are stored separately in `gemini_responses/`, `model_predictions/`, and `nemotron_responses/`.

### Run Automated Test Suite
```powershell
python -m pytest backend/tests -v
```
*(All 14 unit and integration tests pass).*

### Run Production Release Audit
```powershell
python -m ml.evaluate --check-release
```

### Start Backend Server
```powershell
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Start Frontend UI
```powershell
cd frontend
npm.cmd run dev
```
Open `http://localhost:3000` in your browser.
