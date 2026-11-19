"""Generate a SIMULATED forging-shop dataset (precision forged components).

Story baked into the data (so your RCA has something to find):
  * Rejection rises as a die ages (die wear) -> 'Die Wear Mark' & 'Dimensional' defects.
  * Night shift (C) has slightly higher rejection.
  * Machine FP-03 runs hotter -> more 'Scale Pit' and 'Lap' defects.
  * ~3% dirty rows of each kind are injected on purpose (duplicates, nulls, negatives,
    out-of-range values) to exercise the validation layer.
"""
import numpy as np
import pandas as pd
from config import RAW_DIR

rng = np.random.default_rng(42)
RAW_DIR.mkdir(parents=True, exist_ok=True)

# ---------- master data ----------
parts = pd.DataFrame({
    "part_code": ["PF-101", "PF-102", "PF-103", "PF-104"],
    "part_name": ["Connecting Rod Blank", "Crank Gear Forging", "Flange Yoke", "Hub Flange"],
    "material": ["C45", "EN8", "SAE 4140", "EN19"],
    "dim_nominal_mm": [52.00, 78.50, 64.00, 95.00],
    "dim_lsl_mm": [51.90, 78.35, 63.88, 94.80],
    "dim_usl_mm": [52.10, 78.65, 64.12, 95.20],
    "hardness_min_hrc": [22, 26, 28, 30],
    "hardness_max_hrc": [30, 34, 36, 38],
})
dies = pd.DataFrame({
    "die_id": ["D-101A", "D-101B", "D-102A", "D-103A", "D-103B", "D-104A"],
    "part_code": ["PF-101", "PF-101", "PF-102", "PF-103", "PF-103", "PF-104"],
    "die_life_limit_strokes": [40000, 40000, 35000, 45000, 45000, 30000],
})
machines = pd.DataFrame({
    "machine_id": ["FP-01", "FP-02", "FP-03", "FP-04"],
    "machine_type": ["Forging Press 1600T", "Forging Press 1600T", "Forging Press 2500T", "Forging Press 2500T"],
})
parts.to_csv(RAW_DIR / "master_parts.csv", index=False)
dies.to_csv(RAW_DIR / "master_dies.csv", index=False)
machines.to_csv(RAW_DIR / "master_machines.csv", index=False)

# ---------- lot-level data ----------
DEFECTS = ["Lap", "Crack", "Underfill", "Dimensional", "Scale Pit", "Die Wear Mark"]
N_LOTS = 900
dates = pd.date_range("2025-10-01", periods=120, freq="D")
shifts = ["A", "B", "C"]  # C = night

parts_i = parts.set_index("part_code")
die_strokes = {d: int(rng.integers(0, 8000)) for d in dies.die_id}
lots, rejections, measures = [], [], []

for i in range(1, N_LOTS + 1):
    die = dies.iloc[int(rng.integers(0, len(dies)))]
    part = parts_i.loc[die.part_code]
    machine = str(rng.choice(machines.machine_id))
    shift = str(rng.choice(shifts, p=[0.4, 0.35, 0.25]))
    date = dates[int((i / N_LOTS) * (len(dates) - 1))]
    produced = int(rng.integers(400, 1200))
    inspected = int(produced * rng.uniform(0.15, 0.30))

    die_strokes[die.die_id] += produced
    if die_strokes[die.die_id] > die.die_life_limit_strokes * 1.05:
        die_strokes[die.die_id] = int(rng.integers(0, 1500))  # die replaced / re-sharpened
    wear = min(die_strokes[die.die_id] / die.die_life_limit_strokes, 1.5)

    base = 0.012 + 0.05 * wear ** 2
    base *= 1.25 if shift == "C" else 1.0
    base *= 1.3 if machine == "FP-03" else 1.0
    rej_rate = min(base * rng.uniform(0.7, 1.3), 0.25)
    rejected = int(rng.binomial(inspected, rej_rate))

    w = np.array([0.15, 0.08, 0.15, 0.20, 0.12, 0.10]) + np.array([0, 0, 0, 0.25, 0, 0.35]) * wear
    if machine == "FP-03":
        w = w + np.array([0.10, 0, 0, 0, 0.15, 0])
    w = w / w.sum()
    lot_id = f"L{i:05d}"
    if rejected > 0:
        for d, q in zip(DEFECTS, rng.multinomial(rejected, w)):
            if q > 0:
                rejections.append({"lot_id": lot_id, "defect_type": d, "qty": int(q)})

    hardness = round(float(rng.normal((part.hardness_min_hrc + part.hardness_max_hrc) / 2, 1.6)), 1)
    drift = 0.004 * wear  # dimension drifts with die wear
    for s in range(1, 6):
        measures.append({
            "lot_id": lot_id, "sample_no": s,
            "critical_dim_mm": round(float(rng.normal(part.dim_nominal_mm + drift, 0.028)), 3),
        })

    lots.append({
        "lot_id": lot_id, "production_date": date.strftime("%Y-%m-%d"),
        "shift": shift, "machine_id": machine, "part_code": die.part_code, "die_id": die.die_id,
        "die_strokes_at_lot": die_strokes[die.die_id],
        "produced_qty": produced, "inspected_qty": inspected, "rejected_qty": rejected,
        "hardness_hrc": hardness,
    })

lots = pd.DataFrame(lots)
rejections = pd.DataFrame(rejections)
measures = pd.DataFrame(measures)

# ---------- inject dirty data (~3% per issue type) ----------
n_bad = int(len(lots) * 0.03)
idx = rng.choice(lots.index.to_numpy(), size=n_bad * 4, replace=False)
a, b, c, d = idx[:n_bad], idx[n_bad:2 * n_bad], idx[2 * n_bad:3 * n_bad], idx[3 * n_bad:]
lots.loc[a, "inspected_qty"] = -lots.loc[a, "inspected_qty"]                      # negative qty
lots.loc[b, "machine_id"] = None                                                  # missing key
lots.loc[c, "rejected_qty"] = lots.loc[c, "inspected_qty"] + 50                   # rejected > inspected
lots.loc[d, "hardness_hrc"] = 95.0                                                # impossible HRC
lots = pd.concat([lots, lots.sample(8, random_state=1)], ignore_index=True)       # duplicate lot rows
measures.loc[measures.sample(6, random_state=2).index, "critical_dim_mm"] = None  # missing measurement

lots.to_csv(RAW_DIR / "lot_inspection.csv", index=False)
rejections.to_csv(RAW_DIR / "rejection_details.csv", index=False)
measures.to_csv(RAW_DIR / "dimension_measurements.csv", index=False)
print(f"Generated: {len(lots)} lot rows, {len(rejections)} rejection rows, {len(measures)} measurements -> {RAW_DIR}")
