"""
pool_and_train.py
pool_and_train.py
One script: load all effort datasets -> harmonise -> remove duplicates -> train ONE model
-> save ONE final file.

Usage (Windows):
    python pool_and_train.py "D:/KLE fest 2/Models/Data"

Outputs (in <DATA>\pooled\):
    SEERA_POOLED_final.joblib     the single final model bundle
    POOLED_final_dataset.csv      the harmonised, de-duplicated training table
    pooled_cv_results.csv         model comparison
    pooled_per_dataset.csv        pooled model vs. each dataset trained alone
    pooled_dedup_log.txt          what was loaded, skipped and removed
"""
import csv, io, re, sys, warnings
from pathlib import Path
import numpy as np
import pandas as pd
import joblib
from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.model_selection import KFold, cross_val_predict
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
warnings.filterwarnings("ignore")

# ------------------------------------------------------------------ settings
DATA = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"D:\KLE fest 2\Models\Data")
OUT = DATA / "pooled"
OUT.mkdir(parents=True, exist_ok=True)

HOURS_PER_PERSON_MONTH = 152.0
SEERA_EFFORT_UNIT = "hours"      # CONFIRM: SEERA paper says person-months; values look like hours
MIN_ROWS_OWN_TEST = 20           # minimum rows for a dataset to get its own baseline / LOFO test

LOG = []
def log(*parts):
    s = " ".join(str(p) for p in parts)
    LOG.append(s); print(s)

# ------------------------------------------------------------------ readers
def load_arff(path):
    names, rows, in_data = [], [], False
    for line in open(path, encoding="latin-1"):
        s = line.strip()
        if not s or s.startswith("%"):
            continue
        if s.lower().startswith("@attribute"):
            m = re.match(r"@attribute\s+('([^']*)'|\S+)", s, re.I)
            names.append((m.group(2) if m.group(2) is not None else m.group(1)).strip())
        elif s.lower().startswith("@data"):
            in_data = True
        elif in_data:
            rows.append(next(csv.reader(io.StringIO(s), quotechar="'")))
    return pd.DataFrame(rows, columns=names)

def read_table(path):
    if path.suffix.lower() == ".arff":
        df = load_arff(path)
    else:
        df = pd.read_csv(path, encoding_errors="replace")
    df.columns = [str(c).strip() for c in df.columns]
    return df.replace({"?": np.nan, "N/A": np.nan, "": np.nan})

def num(s):
    s = s.astype(str).str.replace(r"\\?%", "", regex=True).str.strip()
    return pd.to_numeric(s.replace({"nan": np.nan}), errors="coerce")

# ------------------------------------------------------------------ harmonisers
# Each returns the common schema:
# source_family, project_key, year, size_type, size_value, effort_hours
def from_seera(d):
    key = d["projID"].astype(str) if "projID" in d else pd.Series(np.arange(1, len(d) + 1)).astype(str)
    factor = 1.0 if SEERA_EFFORT_UNIT == "hours" else HOURS_PER_PERSON_MONTH
    return pd.DataFrame({
        "source_family": "SEERA", "project_key": "SEERA:" + key.values,
        "year": num(d["Year of project"]).values, "size_type": "ObjectPoints",
        "size_value": num(d["Object points"]).values,
        "effort_hours": (num(d["Actual effort"]) * factor).values})

def from_nasa93(d):
    key = d["recordnumber"].astype(str) if "recordnumber" in d else pd.Series(np.arange(1, len(d) + 1)).astype(str)
    return pd.DataFrame({
        "source_family": "NASA93", "project_key": "NASA93:" + key.values,
        "year": num(d["year"]).values, "size_type": "KLOC",
        "size_value": num(d["equivphyskloc"]).values,
        "effort_hours": (num(d["act_effort"]) * HOURS_PER_PERSON_MONTH).values})

def from_isbsg(d):
    eff = num(d["N_effort"]).fillna(num(d["N_effort_level1"]))   # ISBSG effort is already hours
    key = d["ID"].astype(str) if "ID" in d else pd.Series(np.arange(1, len(d) + 1)).astype(str)
    return pd.DataFrame({
        "source_family": "ISBSG", "project_key": "ISBSG:" + key.values,
        "year": num(d["Year"]).values, "size_type": "FunctionPoints",
        "size_value": num(d["FS"]).values, "effort_hours": eff.values})

HARMONISERS = {"seera": from_seera, "nasa": from_nasa93, "isbsg": from_isbsg}

def route(path):
    """Pick a harmoniser from the file name."""
    n = path.name.lower()
    for key, fn in HARMONISERS.items():
        if key in n:
            return fn
    return None

# ------------------------------------------------------------------ load everything
frames, skipped = [], []
candidates = sorted(p for p in DATA.iterdir() if p.is_file() and p.suffix.lower() in (".arff", ".csv"))
log("Files found in", DATA)
for p in candidates:
    fn = route(p)
    if fn is None:
        skipped.append((p.name, "no harmoniser (not SEERA / NASA93 / ISBSG)"))
        continue
    try:
        d = read_table(p)
        h = fn(d)
        h["file"] = p.name
        frames.append(h)
        log(f"  loaded  {p.name:45s} rows={len(h)}")
    except Exception as e:
        skipped.append((p.name, f"could not parse: {e}"))

for name, why in skipped:
    log(f"  skipped {name:45s} {why}")

if not frames:
    raise SystemExit("No datasets loaded. Check the folder path.")
pool = pd.concat(frames, ignore_index=True)
log(f"\nRaw pooled rows: {len(pool)}")

# ------------------------------------------------------------------ clean + de-duplicate
pool["effort_hours"] = pd.to_numeric(pool["effort_hours"], errors="coerce")
pool["size_value"] = pd.to_numeric(pool["size_value"], errors="coerce")
pool["year"] = pd.to_numeric(pool["year"], errors="coerce")

before = len(pool)
pool = pool.dropna(subset=["effort_hours"])
pool = pool[pool["effort_hours"] > 0]
log(f"Dropped missing / non-positive effort: {before - len(pool)}")

before = len(pool)
pool = pool.drop_duplicates("project_key", keep="first")
log(f"Removed same project present in two files (same key): {before - len(pool)}")

before = len(pool)
sig = ["source_family", "effort_hours", "size_value", "year"]
pool = pool.assign(_sig_effort=pool["effort_hours"].round(2),
                   _sig_size=pool["size_value"].round(3))
pool = pool.drop_duplicates(["source_family", "_sig_effort", "_sig_size", "year"], keep="first")
pool = pool.drop(columns=["_sig_effort", "_sig_size"])
log(f"Removed duplicate records with identical effort, size and year: {before - len(pool)}")

pool = pool.reset_index(drop=True)
log(f"Final pooled rows: {len(pool)}")
log(pool.groupby("source_family").size().rename("rows").to_string())

pool.to_csv(OUT / "POOLED_final_dataset.csv", index=False)

# ------------------------------------------------------------------ features and target
def make_X(df):
    return pd.DataFrame({
        "source_family": df["source_family"].values,
        "size_type": df["size_type"].values,
        "log_size": np.log1p(df["size_value"].clip(lower=0)).values,
        "year": df["year"].values,
    })

NUM = ["log_size", "year"]
CAT = ["source_family", "size_type"]

def preprocessor():
    return ColumnTransformer([
        ("num", Pipeline([("imp", SimpleImputer(strategy="median")),
                          ("sc", StandardScaler())]), NUM),
        ("cat", Pipeline([("imp", SimpleImputer(strategy="most_frequent")),
                          ("oh", OneHotEncoder(handle_unknown="ignore", min_frequency=2))]), CAT),
    ])

def wrap(est):
    return TransformedTargetRegressor(est, func=np.log1p, inverse_func=np.expm1)

def build(name):
    if name == "RandomForest":
        est = RandomForestRegressor(n_estimators=500, min_samples_leaf=2, random_state=0, n_jobs=-1)
    else:
        est = GradientBoostingRegressor(n_estimators=300, max_depth=2, learning_rate=0.05,
                                        subsample=0.8, random_state=0)
    return Pipeline([("p", preprocessor()), ("m", wrap(est))])

MODEL_NAMES = ["RandomForest", "GradBoost"]

X = make_X(pool)
y = pool["effort_hours"].reset_index(drop=True)
fam = pool["source_family"].reset_index(drop=True)

def mdmre(yt, yp):
    yp = np.maximum(yp, 1e-6)
    return np.median(np.abs(yt - yp) / yt)

def pred25(yt, yp):
    yp = np.maximum(yp, 1e-6)
    return np.mean(np.abs(yt - yp) / yt <= 0.25)

# ------------------------------------------------------------------ 1) pooled 10-fold x5 CV
REPEATS = 5
cv_rows, oof_store = [], {}
for name in MODEL_NAMES:
    per_rep = []
    preds_all = []
    for r in range(REPEATS):
        p = cross_val_predict(build(name), X, y, cv=KFold(10, shuffle=True, random_state=r))
        preds_all.append(p)
        rep = {"MdMRE": mdmre(y.values, p), "PRED25": pred25(y.values, p),
               "MAE": np.mean(np.abs(y.values - p))}
        for f in pool["source_family"].unique():
            m = (fam == f).values
            rep[f"MdMRE_{f}"] = mdmre(y.values[m], p[m])
        per_rep.append(rep)
    oof_store[name] = preds_all
    cv_rows.append({"model": name, **pd.DataFrame(per_rep).mean().round(3).to_dict()})

cv = pd.DataFrame(cv_rows).sort_values("MdMRE").reset_index(drop=True)
cv.to_csv(OUT / "pooled_cv_results.csv", index=False)
log("\n=== Pooled 10-fold x5 CV (all datasets together) ===")
log(cv.to_string(index=False))

best = cv.iloc[0]["model"]
log(f"\nBest pooled model by MdMRE: {best}")

# ------------------------------------------------------------------ 2) does pooling help each dataset?
rows = []
for f in pool["source_family"].unique():
    m = (fam == f).values
    n = int(m.sum())
    if n < MIN_ROWS_OWN_TEST:
        rows.append({"dataset": f, "rows": n, "own_only_MdMRE": np.nan,
                     "pooled_CV_MdMRE": np.nan, "leave_out_MdMRE": np.nan,
                     "note": "too few rows for a reliable test"})
        continue
    # (a) trained on this dataset alone
    own = []
    for r in range(REPEATS):
        p = cross_val_predict(build(best), X[m], y[m], cv=KFold(min(10, n), shuffle=True, random_state=r))
        own.append(mdmre(y.values[m], p))
    # (b) pooled model, out-of-fold predictions for this dataset
    pooled_m = np.mean([mdmre(y.values[m], oof_store[best][r][m]) for r in range(REPEATS)])
    # (c) train on every OTHER dataset, test on this one (transfer test)
    others = ~m
    lo = build(best).fit(X[others], y[others])
    lo_mdmre = mdmre(y.values[m], lo.predict(X[m]))
    rows.append({"dataset": f, "rows": n, "own_only_MdMRE": round(np.mean(own), 3),
                 "pooled_CV_MdMRE": round(pooled_m, 3), "leave_out_MdMRE": round(lo_mdmre, 3),
                 "note": ""})
per = pd.DataFrame(rows)
per.to_csv(OUT / "pooled_per_dataset.csv", index=False)
log("\n=== Per dataset: own-only vs pooled vs transfer (lower MdMRE is better) ===")
log(per.to_string(index=False))

# ------------------------------------------------------------------ 3) fit ONE final model on everything
final = build(best).fit(X, y)
bundle = {
    "model": final,
    "model_name": best,
    "feature_columns": list(X.columns),
    "source_families": sorted(pool["source_family"].unique().tolist()),
    "target": "effort_hours (person-hours)",
    "effort_unit_assumption": {"SEERA": SEERA_EFFORT_UNIT, "NASA93": "person-months x152",
                               "ISBSG": "hours"},
    "training_rows": int(len(pool)),
    "cv_summary": cv.iloc[0].to_dict(),
}
joblib.dump(bundle, OUT / "SEERA_POOLED_final.joblib")
(OUT / "pooled_dedup_log.txt").write_text("\n".join(LOG), encoding="utf-8")
log(f"\nSaved final model : {OUT / 'SEERA_POOLED_final.joblib'}")
log(f"Saved training data: {OUT / 'POOLED_final_dataset.csv'}")
log(f"Saved log         : {OUT / 'pooled_dedup_log.txt'}")
