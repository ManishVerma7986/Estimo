# Raw Datasets Directory

This directory stores unmodified raw dataset uploads (`data/raw/<dataset_id>/`).
By default, this repository starts in an **EMPTY STATE** per Rule R1:
> "NO DUMMY DATA. Never create, generate, simulate, or hardcode fake projects, prices, labor rates, BOM items, historical actuals, metrics, or model files."

Import datasets via the User Interface (Datasets page) or via the CLI:
```bash
python -m ml.data_ingestion --file <path> --name <name> --domain <domain> --license <license> --source <source>
```
