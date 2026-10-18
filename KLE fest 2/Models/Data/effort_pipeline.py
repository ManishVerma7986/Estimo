"""
Software effort prediction engine: SEERA (main), NASA93, ISBSG10.
Usage:
    python effort_pipeline.py            # clean, cross-validate, train, save models
    from effort_pipeline import predict  # use saved model on new rows
"""
import re, sys, warnings, joblib
import numpy as np, pandas as pd
from scipy.io import arff
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.model_selection import KFold, cross_val_predict
from sklearn.linear_model import RidgeCV
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.neighbors import KNeighborsRegressor
from sklearn.compose import TransformedTargetRegressor
warnings.filterwarnings("ignore")
UP = "/mnt/user-data/uploads/"
OUT = "/mnt/user-data/outputs/"

# ---------------------------------------------------------------- loaders
def load_arff(path):
    # SEERA files use \r\n and 'N/A' tokens; scipy chokes on some nominal quirks, so fall back to a manual parser
    try:
        data, meta = arff.loadarff(path)
        df = pd.DataFrame(data)
        for c in df.columns:
            if df[c].dtype == object:
                df[c] = df[c].apply(lambda v: v.decode() if isinstance(v, bytes) else v)
        return df
    except Exception:
        names, rows, in_data = [], [], False
        for line in open(path, encoding="latin-1"):
            s = line.strip()
            if not s or s.startswith("%"): continue
            if s.lower().startswith("@attribute"):
                m = re.match(r"@attribute\s+('([^']*)'|\S+)", s, re.I)
                names.append(m.group(2) if m.group(2) is not None else m.group(1))
            elif s.lower().startswith("@data"): in_data = True
            elif in_data:
                import csv, io
                rows.append(next(csv.reader(io.StringIO(s), quotechar="'")))
        return pd.DataFrame(rows, columns=names)

def to_num(s):
    return pd.to_numeric(s.astype(str).str.replace(r"\\?%", "", regex=True)
                          .str.strip().replace({"?": np.nan, "N/A": np.nan, "nan": np.nan, "": np.nan}),
                         errors="coerce")

# ---------------------------------------------------------------- SEERA
SEERA_TARGET = "Actual effort"
# nominal codes (no natural order) -> one-hot ; everything else numeric/ordinal
SEERA_NOMINAL = ["Organization type", "Role in organization", "Customer organization type",
                 "Development type", "Application domain", "Methodology",
                 "Programming language used", "DBMS used", "Team selection", "Other sizing method"]
# known only AFTER the project finishes -> target leakage, remove
SEERA_LEAK = ["Actual duration", "% project gain (loss)", "\\% project gain (loss)",
              "Team continuity", "Outsourcing impact", "ProjID", "Organization id",
              "Estimated size"]          # id columns + ~all N/A

def clean_seera(keep_estimated_effort=True):
    df = load_arff(UP + "ARFF__SEERA_cost_estimation_dataset_csv.arff")
    df.columns = [c.strip() for c in df.columns]
    leak = [c.strip() for c in SEERA_LEAK]
    df = df.drop(columns=[c for c in leak if c in df.columns])
    if not keep_estimated_effort:
        df = df.drop(columns=["Estimated effort"])
    y = to_num(df.pop(SEERA_TARGET))
    nom = [c for c in SEERA_NOMINAL if c in df.columns]
    X = pd.DataFrame(index=df.index)
    for c in df.columns:
        if c in nom: X[c] = df[c].astype(str).replace({"?": np.nan, "nan": np.nan})
        else:        X[c] = to_num(df[c])
    ok = y.notna() & (y > 0)
    return X[ok].reset_index(drop=True), y[ok].reset_index(drop=True), nom

# ---------------------------------------------------------------- NASA93
NASA_ORD = ["rely","data","cplx","time","stor","virt","turn","acap","aexp","pcap","vexp","lexp","modp","tool","sced"]
def clean_nasa():
    df = load_arff(UP + "nasa93.arff")
    y = to_num(df.pop("act_effort"))
    df = df.drop(columns=["recordnumber", "projectname"])
    order = {k: i for i, k in enumerate(["vl", "l", "n", "h", "vh", "xh"])}
    for c in NASA_ORD: df[c] = df[c].map(order).astype(float)
    df["equivphyskloc"] = to_num(df["equivphyskloc"])
    df["year"] = to_num(df["year"])
    X = df
    return X, y, ["cat2", "forg", "center", "mode"]

# ---------------------------------------------------------------- ISBSG10
def clean_isbsg():
    df = load_arff(UP + "isbsg10.arff")
    df = df.replace({"?": np.nan})
    y = to_num(df["N_effort"]).fillna(to_num(df["N_effort_level1"]))
    # drop leakage: any effort/defect/after-the-fact columns, IDs, free text, dates
    drop = [c for c in df.columns if re.search(r"effort|PDR|SDR|PET|PIT|Defects|ID$|Date|^DDE|E_Comments|Hardware1|E_Estimate|C_Estimate|EC_Date|Language1", c, re.I)]
    df = df.drop(columns=drop)
    keep_nominal, X = [], pd.DataFrame(index=df.index)
    for c in df.columns:
        num = to_num(df[c])
        if num.notna().sum() >= 0.8 * df[c].notna().sum() and df[c].notna().any(): X[c] = num
        else: X[c] = df[c].astype(object); keep_nominal.append(c)
    X = X.loc[:, X.isna().mean() < 0.6]                # drop columns >60% missing
    X = X.loc[:, X.nunique(dropna=True) > 1]            # drop constant columns
    keep_nominal = [c for c in keep_nominal if c in X.columns]
    ok = y.notna() & (y > 0)
    return X[ok].reset_index(drop=True), y[ok].reset_index(drop=True), keep_nominal

# ---------------------------------------------------------------- modelling
def make_preprocessor(X, nominal):
    num = [c for c in X.columns if c not in nominal]
    return ColumnTransformer([
        ("num", Pipeline([("imp", SimpleImputer(strategy="median", add_indicator=False)),
                          ("sc", StandardScaler())]), num),
        ("cat", Pipeline([("imp", SimpleImputer(strategy="most_frequent")),
                          ("oh", OneHotEncoder(handle_unknown="ignore", min_frequency=3))]), nominal),
    ])

def log_model(est):  # effort is heavily right-skewed -> train on log(effort)
    return TransformedTargetRegressor(est, func=np.log1p, inverse_func=np.expm1)

def models(X, nominal):
    pre = lambda: make_preprocessor(X, nominal)
    return {
        "Ridge":         Pipeline([("p", pre()), ("m", log_model(RidgeCV(alphas=np.logspace(-2, 3, 20))))]),
        "RandomForest":  Pipeline([("p", pre()), ("m", log_model(RandomForestRegressor(500, min_samples_leaf=2, random_state=0, n_jobs=-1)))]),
        "GradBoost":     Pipeline([("p", pre()), ("m", log_model(GradientBoostingRegressor(n_estimators=300, max_depth=2, learning_rate=0.05, subsample=0.8, random_state=0)))]),
        "kNN":           Pipeline([("p", pre()), ("m", log_model(KNeighborsRegressor(5, weights="distance")))]),
    }

def metrics(y, p):
    p = np.maximum(p, 1e-6); mre = np.abs(y - p) / y
    return dict(MAE=np.mean(np.abs(y - p)), MdAE=np.median(np.abs(y - p)),
                MMRE=mre.mean(), MdMRE=np.median(mre), PRED25=(mre <= .25).mean(),
                SA=1 - np.mean(np.abs(y - p)) / np.mean(np.abs(y - np.median(y))))  # skill vs. median guess

def evaluate(name, X, y, nominal, repeats=5):
    rows = []
    for mname, m in models(X, nominal).items():
        res = []
        for r in range(repeats):
            p = cross_val_predict(m, X, y, cv=KFold(10, shuffle=True, random_state=r))
            res.append(metrics(y.values, p))
        rows.append({"dataset": name, "model": mname, **pd.DataFrame(res).mean().round(3).to_dict()})
    return pd.DataFrame(rows)

def main():
    sets = {"SEERA": clean_seera(True), "SEERA_noEstEffort": clean_seera(False),
            "NASA93": clean_nasa(), "ISBSG10": clean_isbsg()}
    allres = []
    for name, (X, y, nom) in sets.items():
        print(f"\n== {name}: {X.shape[0]} rows, {X.shape[1]} features, "
              f"{X.isna().mean().mean():.1%} missing, effort median={y.median():.0f}, max={y.max():.0f}")
        r = evaluate(name, X, y, nom); print(r.to_string(index=False)); allres.append(r)
        best = r.sort_values("MdMRE").iloc[0]["model"]
        final = models(X, nom)[best].fit(X, y)
        joblib.dump({"model": final, "columns": list(X.columns), "best": best}, OUT + f"model_{name}.joblib")
    pd.concat(allres).to_csv(OUT + "cv_results.csv", index=False)
    for n, (X, y, nom) in sets.items():
        X.assign(effort=y).to_csv(OUT + f"clean_{n}.csv", index=False)

def predict(new_rows: pd.DataFrame, dataset="SEERA"):
    """new_rows must use the same column names as the cleaned training features."""
    bundle = joblib.load(OUT + f"model_{dataset}.joblib")
    return bundle["model"].predict(new_rows.reindex(columns=bundle["columns"]))

if __name__ == "__main__":
    main()
