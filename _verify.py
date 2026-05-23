"""Verify the Framework v0.6 worked example from the revised filtering/scoring document."""

import pandas as pd
from vector import build_vector
from scoring import filter_skus, score_skus

ans = {
    "setting": "large_commercial",
    "job": "lift_and_store",
    "source": "borewell",
    "lift": "floors_11_15",
    "demand": "vol_50000",
    "c1_casing": "casing_6in",
    "c2_depth": "200_300ft",
    "c7_phase": "Three",
    "c8_duty": "heavy",
    "c9_min_v": 380,
    "c9_max_v": 430,
}

vec = build_vector(ans)
print("=== Requirement Vector ===")
for k, v in vec.items():
    print(f"  {k}: {v}")

df = pd.read_excel("FINAL_MASTER_DATASHEET_final.xlsx", sheet_name="Master Data")
print(f"\nLoaded {len(df)} catalogue rows")

survivors, trace = filter_skus(df, vec)
print("\n=== Filter trace ===")
for t in trace:
    print(f"  Step {t['step']}: {t['label']} → {t['rows_left']}")

scored = score_skus(survivors, vec)
print(f"\n=== Survivors after filtering: {len(scored)} (doc expects 114) ===")

cols = [
    "Brand",
    "SKU",
    "HP",
    "Min Head (m)",
    "Max Head (m)",
    "Min Flow (LPH)",
    "Max Flow (LPH)",
    "Phase",
    "Pump Diameter",
    "head_score",
    "flow_score",
    "penalties",
    "score",
]
print(scored.head(5)[cols].to_string(index=False))

print("\n=== Doc expectation for Top 5 ===")
print("1 CRI Pumps CRI4R-2N/3/35      3.0 HP  32-261 m  0-25200 LPH  Both   V4  99")
print("2 Kirloskar Brothers 80HHN-2024 20 HP   76-216 m  0-25200 LPH  Three  V6  99")
print("3 CRI Pumps CRI4R-2/3/40       3.0 HP  22-278 m  0-25200 LPH  Both   V4  98")
print("4 CRI Pumps CRI4R-2N/3/32      3.0 HP  40-241 m  0-25200 LPH  Both   V4  98")
print("5 CRI Pumps CRI4R-3E/5/40      5.0 HP   4-301 m  0-25200 LPH  Both   V4  98")
