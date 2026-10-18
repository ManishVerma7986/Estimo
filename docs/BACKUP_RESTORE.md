# Backup and Restore Procedure

## 1. What to Backup
The offline-first architecture organizes all critical assets under explicit local directories:

| Component | Path | Description |
|-----------|------|-------------|
| **Raw Datasets** | `data/raw/` | Unmodified uploaded raw datasets (`.csv`, `.arff`, `.xlsx`, `.parquet`) |
| **Manifests** | `data/manifests/` | Cryptographic SHA-256 manifests and data quality summaries |
| **Model Artifacts** | `models/<target>/<version>/` | Fitted scikit-learn/XGBoost pipelines, evaluation metrics, schemas |
| **Model Registry** | `models/registry.json` | Active model pointers and signed checksums |
| **Audit & Reports** | `reports/` | Released audits, estimate history, and recorded actuals |
| **Schema Templates**| `configs/schemas/` | User-defined column mapping definitions |

---

## 2. Backup Command
To create a timestamped backup archive on Windows PowerShell:
```powershell
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
Compress-Archive -Path "data", "models", "configs", "reports" -DestinationPath "estimo_backup_$timestamp.zip"
```

---

## 3. Restore Command
To restore from an archive:
```powershell
Expand-Archive -Path "estimo_backup_<timestamp>.zip" -DestinationPath "." -Force
```

---

## 4. Post-Restore Verification
After restoring, execute the integrity audit to ensure all restored model files match their recorded SHA-256 signatures:
```powershell
python -m ml.registry verify
python -m ml.evaluate --check-release
```
Both commands must report 100% VALID signatures and exit with code 0.
