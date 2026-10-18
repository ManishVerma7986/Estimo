# KLE Fest 2 - Integrated Estimo Project Estimator

This Flask application accepts project requirements as text, an image, or a PDF and runs a three-part estimate:

1. **Requirements extraction:** Gemini returns hardware requirements and a software full-scope payload (BOM, labor, taxes, effort features, target, and analogy dataset). The exact raw provider text and normalized payload are shown in the progress panel.
2. **Parallel estimates:** The existing KLE Fest 2 hardware agent searches product listings and prices. The software payload goes to Estimo's shared estimation service, which loads approved models from `cost_estimation_ai/models/` through its checksummed registry and computes baseline costs, Monte Carlo uncertainty, ML prediction, and historical analogies.
3. **Nemotron interpretation:** Nemotron receives the completed estimates and produces a separate narrative summary. It does not replace or alter any numeric result. A final deterministic local step combines the hardware and software cost ranges.

The frontend displays each step's output in an expandable progress card. Generated files are stored locally:

- `../../gemini_responses/`: exact Gemini response text and normalized requirement JSON.
- `../../model_predictions/`: exact local ML result and combined estimate JSON.
- `../../nemotron_responses/`: raw Nemotron summary and any Nemotron fallback response.

## Run

From this directory:

```powershell
python app.py
```

Open `http://127.0.0.1:5002`. Configure Gemini and NVIDIA credentials using the existing `Nvidea/image.py` configuration / `Nvidea/key.txt`. Live hardware price search also requires TinyFish CLI.

The local model registry and artifacts must exist in the parent Estimo project under `models/`. The model path and version are included in each successful local prediction output.
