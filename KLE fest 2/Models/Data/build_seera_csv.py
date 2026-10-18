"""
Builds one combined CSV from all SEERA files.
Output:
  SEERA_master_wide.csv        120 rows = projects. Main 76 attributes (from ARFF) + every
                               raw sub-attribute from the 8 category sheets, joined on projID.
  SEERA_subattributes_raw.csv  Only the raw sub-attribute sheets, flattened (wide), projID key.
  SEERA_main76.csv             Main 76 attributes with ? / N/A normalised.
  NASA93_clean.csv, ISBSG10_clean.csv
  SEERA_codebook.csv           Column -> source sheet, header group, and missing-value count.
  SEERA_reconciliation.txt     Checks: ARFF vs XLSX vs per-category ARFF agreement.
"""
import re, csv, io
import numpy as np, pandas as pd
from scipy.io import arff

UP, OUT = "/mnt/user-data/uploads/", "/mnt/user-data/outputs/"
MISSING = {"?", "N/A", "NA", "nan", "", "None"}
log = []

def norm_val(v):
    if isinstance(v, str):
        s = v.strip()
        if s in MISSING: return np.nan
        if s in ("True", "False"): return int(s == "True")
        s2 = s.replace("\\%", "").replace("%", "")
        try: return float(s2)
        except ValueError: return s
    if isinstance(v, (bool, np.bool_)): return int(v)
    return v

# ---------- 1. raw workbook: flatten two-row headers per sheet ----------
def flatten_sheet(sheet):
    raw = pd.read_excel(UP + "SEERA_dataset_original_raw_data.xlsx", sheet_name=sheet, header=None)
    r0 = raw.iloc[0].tolist(); r1 = raw.iloc[1].tolist()
    grp, last = [], ""
    for v in r0:                                     # forward-fill group header
        if pd.notna(v) and str(v).strip(): last = str(v).strip()
        grp.append(last)
    sub = ["" if pd.isna(v) else str(v).strip() for v in r1]
    names, seen = [], {}
    for g, s in zip(grp, sub):
        name = s if s and s != "nan" else g
        if s and s != "nan" and s != g:
            name = f"{g} | {s}"
        base = name; k = 1
        while name in seen: k += 1; name = f"{base}_{k}"
        seen[name] = 1; names.append(name)
    body = raw.iloc[2:].copy(); body.columns = names
    # keep only real project rows: projID must be numeric
    pid_col = names[0]
    body = body[pd.to_numeric(body[pid_col], errors="coerce").notna()].copy()
    body[pid_col] = body[pid_col].astype(int)
    body = body.map(norm_val)
    body = body.rename(columns={pid_col: "projID"})
    return body

SHEETS = ["General Information", "Size", "Effort", "Environment", "Users", "Developers", "Project", "Product"]
frames = {}
for s in SHEETS:
    df = flatten_sheet(s)
    df = df.loc[:, ~df.columns.duplicated()]
    df.columns = [f"{s} :: {c}" if c != "projID" else c for c in df.columns]
    frames[s] = df
    log.append(f"sheet '{s}': {df.shape[0]} projects, {df.shape[1]-1} columns")

raw = frames[SHEETS[0]]
for s in SHEETS[1:]:
    raw = raw.merge(frames[s], on="projID", how="outer")
raw = raw.sort_values("projID").reset_index(drop=True)
log.append(f"merged raw sub-attributes: {raw.shape}, unique projIDs={raw.projID.nunique()}")

# ---------- 2. main 76 attributes from ARFF ----------
def load_arff_df(path):
    try:
        data, _ = arff.loadarff(path); df = pd.DataFrame(data)
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
                rows.append(next(csv.reader(io.StringIO(s), quotechar="'")))
        return pd.DataFrame(rows, columns=[n.strip() for n in names])

main = load_arff_df(UP + "ARFF__SEERA_cost_estimation_dataset_csv.arff")
main.columns = [c.strip() for c in main.columns]
main = main.map(norm_val)
main = main.rename(columns={"ProjID": "projID"})
main["projID"] = main["projID"].astype(int)
main = main.sort_values("projID").reset_index(drop=True)
log.append(f"main ARFF: {main.shape}")

# ---------- 3. reconciliation ----------
xl_main = pd.read_excel(UP + "SEERA_cost_estimation_dataset.xlsx", header=None)
log.append(f"main XLSX (raw read): {xl_main.shape} incl. 2 header rows")
for cat in ["Users", "Effort", "Size"]:
    f = {"Users": "SEERA_Users__csv.arff", "Effort": "SEERA_Effort__csv.arff", "Size": "SEERA_Size__csv.arff"}[cat]
    a = load_arff_df(UP + f)
    log.append(f"per-category ARFF {f}: {a.shape} rows x cols; sheet rows for {cat}={len(frames[cat])}")

# The main ARFF's Actual effort should equal the raw workbook's Actual effort
ae_raw = raw.set_index("projID")["Effort :: Actual effort"] if "Effort :: Actual effort" in raw else None
if ae_raw is not None:
    m = main.set_index("projID")["Actual effort"]
    common = m.index.intersection(ae_raw.dropna().index)
    diff = (m.loc[common].astype(float) - ae_raw.loc[common].astype(float)).abs()
    log.append(f"Actual effort ARFF vs raw sheet: {len(common)} projects compared, {int((diff>0.5).sum())} mismatches")

# ---------- 4. master wide file ----------
main_renamed = main.copy()
main_renamed.columns = ["projID"] + [f"MAIN :: {c}" for c in main.columns if c != "projID"]
master = main_renamed.merge(raw, on="projID", how="outer", indicator="src")
log.append("join status (main vs raw): " + str(master["src"].value_counts().to_dict()))
master = master.drop(columns="src")
master.to_csv(OUT + "SEERA_master_wide.csv", index=False)
raw.to_csv(OUT + "SEERA_subattributes_raw.csv", index=False)
main.to_csv(OUT + "SEERA_main76.csv", index=False)

# ---------- 5. codebook ----------
cb = []
for c in master.columns:
    src = "MAIN ARFF" if c.startswith("MAIN ::") else ("RAW XLSX: " + c.split(" :: ")[0] if " :: " in c else "RAW XLSX")
    cb.append({"column": c, "source": src, "non_missing": int(master[c].notna().sum()),
               "missing": int(master[c].isna().sum()), "dtype": str(master[c].dtype)})
pd.DataFrame(cb).to_csv(OUT + "SEERA_codebook.csv", index=False)

# ---------- 6. NASA93 and ISBSG10 (cleaned, separate: different projects) ----------
nasa = load_arff_df(UP + "nasa93.arff")
nasa.columns = [c.strip() for c in nasa.columns]
nasa = nasa.map(norm_val); nasa.to_csv(OUT + "NASA93_clean.csv", index=False)
isb = load_arff_df(UP + "isbsg10.arff")
isb.columns = [c.strip() for c in isb.columns]
isb = isb.replace({"?": np.nan}); isb.to_csv(OUT + "ISBSG10_clean.csv", index=False)
log.append(f"NASA93: {nasa.shape}; ISBSG10: {isb.shape}")

open(OUT + "SEERA_reconciliation.txt", "w").write("\n".join(log) + "\n")
print("\n".join(log))
