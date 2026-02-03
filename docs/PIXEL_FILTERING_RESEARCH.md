# Pixel Filtering: Correct Approach vs Main Branch vs Current State vs ECO_Converted.py

This doc compares pixel filtering for ECOSTRESS L2T LSTE (`ECO_L2T_LSTE.002`), layers: LST, LST_err, QC, water, cloud, EmisWB, height.

- **Main branch** = `lambda_functions/processor.py` **before** the QC fix (as it was on main).
- **Current state** = same lambda **after** the QC fix (bit-mask QC).
- **ECO_Converted.py** = old processing code (e.g. [Abdullah-Usmani/sat-water-temps](https://github.com/Abdullah-Usmani/sat-water-temps/blob/main/ECO_Converted.py) or local `ECO_Converted.py`).

| | **Correct approach** (ECOSTRESS spec) | **Main branch** (lambda before fixes) | **Current state** (lambda after fixes) | **ECO_Converted.py** (old code) |
|--|--|--|--|--|
| **QC** | Bit mask: keep `(QC != 65535) and (QC & 3) <= 1` | Blacklist `{15, 2501, 3525, 65535}` ❌ | Bit mask ✅ | Blacklist ❌ |
| **Cloud** | Reject `cloud == 1` | ✅ | ✅ | ✅ |
| **Water** | Water detected → keep `wt==1`; no water → keep all, flag | ✅ | ✅ | No water → keep only `wt==1` → **empty** ❌ |

---

## 1. QC (Quality Control)

### Correct approach (ECOSTRESS spec)

- QC is **16-bit**; only **bits 0–1** are mandatory QA for LSTE.
- Bits 0–1: **0** = perfect, **1** = nominal (keep); **2** = cloud, **3** = not produced (reject).
- **Fill:** 65535 = no data (reject).
- Rule: **keep** `(QC != 65535) and (QC & 0x03) <= 1`; **reject** non-finite, fill, and `(QC & 0x03) > 1`.

V2 LSTE QC does **not** encode cloud in these bits; cloud must come from the **cloud** layer ([LP DAAC notice](https://lpdaac.usgs.gov/news/ecostress-version-2-level-2-quality-flags-action-required-for-accurate-quality-information/)).

### Main branch (lambda before fixes)

Used the same blacklist as ECO_Converted.py:

```python
INVALID_QC_VALUES = {15, 2501, 3525, 65535}
# ...
df[f"{col}_filter"] = np.where(
    df["QC"].isin(INVALID_QC_VALUES), np.nan, df[col]
)
```

**Problems:** Over-rejects nominal (2501, 3525 have bits 0–1 = 1). Under-rejects cloud/not-produced (2, 3, 6, 7 not in set). Same bug as ECO_Converted.py.

**Verdict:** ❌ Wrong vs spec.

### Current state (lambda after fixes)

Uses bit-mask logic:

```python
QC_FILL_VALUE = 65535
QC_MANDATORY_MASK = 0x03
qc = np.asarray(df["QC"], dtype=np.int32)
qc_invalid = (
    ~np.isfinite(df["QC"].values)
    | (qc == QC_FILL_VALUE)
    | ((qc & QC_MANDATORY_MASK) > 1)
)
for col in ["LST", "LST_err", "QC", "EmisWB", "height"]:
    df[f"{col}_filter"] = np.where(qc_invalid, np.nan, df[col])
```

**Verdict:** ✅ Matches correct approach.

### ECO_Converted.py (old)

Same blacklist as main-branch lambda before fixes: `INVALID_QC_VALUES = {15, 2501, 3525, 65535}`. Same over/under-reject issues.

**Verdict:** ❌ Wrong vs spec.

---

## 2. Cloud

### Correct approach

Use the **cloud** layer: **0** = clear, **1** = cloudy. Reject pixels where cloud == 1.

### Main branch / Current state / ECO_Converted.py

All three use `np.where(df["cloud"] == 1, np.nan, ...)`. No change in the fix.

**Verdict:** ✅ Correct in all.

---

## 3. Water mask

### Correct approach

- **Encoding:** 1 = water, 0 = land.
- If **any** pixel has `wt == 1`: keep only water pixels (`wt == 1`).
- If **no** pixel has `wt == 1`: **do not** filter by water; keep all pixels and flag (e.g. suffix `_wtoff`).

### Main branch (lambda before fixes)

```python
water_mask_flag = df["wt"].isin([1]).any()
if water_mask_flag:
    df[f"{col}"] = np.where(df["wt"] == 0, np.nan, df[col])
else:
    suffix = "_wtoff"
```

**Verdict:** ✅ Correct. No water → keep all, suffix `_wtoff`. (Only QC was changed in the fix.)

### Current state (lambda after fixes)

Same water logic as main branch. Unchanged by the fix.

**Verdict:** ✅ Correct.

### ECO_Converted.py (old)

```python
water_mask_flag = df["wt"].isin([1]).any()
# ...
if not water_mask_flag:
    for col in ["LST_filter", ...]:
        df[f"{col}"] = np.where(df["wt"] == 0, np.nan, df[col])  # keep only wt==1
    filter_csv_path = ... filter_wtoff.csv
```

When **no** water is detected, it keeps only `wt == 1` → there are none → **all pixels NaN**. `_wtoff` outputs are **empty**.

**Verdict:** ❌ Wrong. Inverted “no water” branch.

---

## Summary table

| Step | Correct approach | Main branch (before fix) | Current state (after fix) | ECO_Converted.py |
|------|------------------|-------------------------|---------------------------|------------------|
| **QC** | Bit mask (keep 0/1, reject fill & 2/3) | ❌ Blacklist | ✅ Bit mask | ❌ Blacklist |
| **Cloud** | Reject cloud == 1 | ✅ | ✅ | ✅ |
| **Water when water detected** | Keep only wt == 1 | ✅ | ✅ | ✅ |
| **Water when no water detected** | Keep all; flag `_wtoff` | ✅ | ✅ | ❌ Keep only wt==1 → empty |

**What changed in the fix:** Only QC. Main-branch lambda already had correct cloud and water logic; it had the same QC blacklist bug as ECO_Converted.py. The fix replaced the blacklist with bit-mask QC filtering. ECO_Converted.py still has both the QC bug and the water (no-water) bug.

---

## References

- [ECOSTRESS-QC-Flag](https://github.com/ECOSTRESS-Tutorials/ECOSTRESS-QC-Flag) – bits 0–1 (`QC & 0b11`), keep 0/1.
- [Exploring ECOSTRESS L2T LSTE (VITALS)](https://nasa.github.io/VITALS/python/Exploring_ECOSTRESS_L2T_LSTE.html) – 16-bit QC, use cloud layer.
- [LP DAAC – ECOSTRESS V2 Level 2 Quality Flags](https://lpdaac.usgs.gov/news/ecostress-version-2-level-2-quality-flags-action-required-for-accurate-quality-information/) – use cloud mask, not QC, for clouds.
- `WATER_DETECTION_ANALYSIS.md` – GAM4water fallback when built-in water mask is unreliable.
