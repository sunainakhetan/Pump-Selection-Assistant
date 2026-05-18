"""Verify the worked example from FILTERING_AND_SCORING_MECHANISM doc §9-15."""
import sys
sys.path.insert(0, '/home/claude/pump_app')

import pandas as pd
from vector import build_vector
from scoring import filter_skus, score_skus

# Worked-example answers (doc section 9). The doc explicitly uses 18m/25m and
# 6 outlets to preserve the original math, so we set 3rd floor + outlets=6.
ans = {
    "job": "boost_pressure",
    "source": "overhead_tank",
    "lift": "floor_3",          # 12m / 18m per current LIFT_HEAD; doc overrides to 18/25
    "demand": "medium",
    "setting": "home",
    "c4_outlets": "5_12",
    "c4_outlets_count": 6,      # doc uses 6 to preserve worked-example math
    "c5_usage": "moderate",
    "c7_phase": "Single",
    "c9_voltage": "normal",
}

# The doc explicitly forces 18/25 instead of the floor_3 default 12/18 for this
# worked example (it explains the difference inline). To verify exactly against
# the doc's table, override here:
vec = build_vector(ans)
# Apply doc's explicit override for the worked example only:
vec["required_min_head"] = 18.0
vec["typical_head"] = 25.0

print("=== Requirement Vector ===")
for k, v in vec.items():
    print(f"  {k}: {v}")

# Load Excel and run pipeline
df = pd.read_excel("/home/claude/pump_app/FINAL_MASTER_DATASHEET_final.xlsx", sheet_name="Master Data")
print(f"\nLoaded {len(df)} catalogue rows")

survivors, trace = filter_skus(df, vec)
print("\n=== Filter trace ===")
for t in trace:
    print(f"  Step {t['step']}: {t['label']:<60} → {t['rows_left']}")

scored = score_skus(survivors, vec)
print(f"\n=== Survivors after filtering: {len(scored)} (doc expects 101) ===")

print("\n=== Top 5 ===")
cols = ["Brand", "SKU", "Type", "HP", "Min Head (m)", "Max Head (m)",
        "Min Flow (LPH)", "Max Flow (LPH)", "Phase", "head_score", "flow_score",
        "penalties", "score"]
print(scored.head(5)[cols].to_string(index=False))

print("\n=== Doc expectation for Top 5 ===")
print("1 Shakti SH4-3             Hydropneumatic 0.75 9-26  0-7980     Both   96")
print("2 Shakti SHI4-3            Hydropneumatic 0.75 9-26  0-7980     Both   96")
print("3 Shakti SHN4-3            Hydropneumatic 0.75 9-26  0-7980     Both   96")
print("4 Kirloskar CPBS-62824H / V Hydropneumatic 0.80 6-35 1200-6000  Single 94")
print("5 Lubi MH 1A               Hydropneumatic 0.75 12-22 0-7500     Single 93")
