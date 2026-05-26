"""Verify key Framework v0.6 behaviours against the supplied catalogue."""

from pathlib import Path

import pandas as pd

from rules import evaluate
from scoring import filter_skus, score_skus
from vector import build_vector

BASE_DIR = Path(__file__).parent
CATALOGUE_CANDIDATES = [
    BASE_DIR / "FINAL_MASTER_DATASHEET_final.xlsx",
    BASE_DIR / "MASTER DATASHEET_final_final copy(7).xlsx",
]


def catalogue_path() -> Path:
    for path in CATALOGUE_CANDIDATES:
        if path.exists():
            return path
    raise FileNotFoundError(
        "Could not find the catalogue. Expected FINAL_MASTER_DATASHEET_final.xlsx "
        "or MASTER DATASHEET_final_final copy(7).xlsx next to _verify.py."
    )


def verify_worked_example() -> None:
    """Reproduce the revised filtering/scoring document's Large-commercial borewell example."""
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

    df = pd.read_excel(catalogue_path(), sheet_name="Master Data")
    print(f"\nLoaded {len(df)} catalogue rows")

    survivors, trace = filter_skus(df, vec)
    print("\n=== Filter trace ===")
    for t in trace:
        print(f"  Step {t['step']}: {t['label']} → {t['rows_left']}")

    scored = score_skus(survivors, vec)
    print(f"\n=== Survivors after filtering: {len(scored)} (doc expects 114) ===")

    expected = [
        ("CRI Pumps", "CRI4R-2N/3/35", 99),
        ("Kirloskar Brothers", "80HHN-2024", 99),
        ("CRI Pumps", "CRI4R-2/3/40", 98),
        ("CRI Pumps", "CRI4R-2N/3/32", 98),
        ("CRI Pumps", "CRI4R-3E/5/40", 98),
    ]
    top = scored.head(5)
    assert len(scored) == 114, f"Expected 114 survivors; got {len(scored)}"
    for idx, (brand, sku, score) in enumerate(expected):
        row = top.iloc[idx]
        assert row["Brand"] == brand and row["SKU"] == sku and int(row["score"]) == score, (
            f"Top-{idx + 1} mismatch: expected {(brand, sku, score)}, "
            f"got {(row['Brand'], row['SKU'], int(row['score']))}"
        )

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
    print(top[cols].to_string(index=False))
    print("\nWorked example: PASS")


def verify_relaxed_ground_lift_rules() -> None:
    """Check the v0.6 below-grade ground-floor lift changes."""
    borewell_ground = {
        "setting": "home",
        "job": "lift_and_store",
        "source": "borewell",
        "lift": "ground",
        "demand": "vol_800",
        "c0_destination": "ground_sump",
        "c1_casing": "casing_4in",
        "c2_depth": "50_100ft",
        "c7_phase": "Single",
        "c9_voltage_band": "single_normal_200_240",
    }
    assert not [r for r in evaluate(borewell_ground) if r[1] == "hard"], (
        "Borewell → ground-floor lift-and-store should be valid in v0.6."
    )

    sump_direct = {
        "setting": "home",
        "job": "lift_and_pressurise_directly",
        "source": "underground_sump",
        "lift": "ground",
        "demand": "vol_800",
        "c0_destination": "direct_pipes",
        "c4_outlets": "1_4",
        "c4_outlets_count": 2,
        "c5_usage": "moderate",
        "c5a_pressure": "home_standard",
        "c7_phase": "Single",
        "c9_voltage_band": "single_normal_200_240",
    }
    assert not [r for r in evaluate(sump_direct) if r[1] == "hard"], (
        "Underground-sump → ground-floor lift-and-pressurise should be valid in v0.6."
    )
    vec = build_vector(sump_direct)
    assert vec["required_min_head"] == 8 and vec["typical_head"] == 17, (
        "Expected sump-lift allowance of +8 m required / +12 m typical on top of ground lift."
    )
    assert "Pressure Booster Pump" in vec["allowed_pump_types"], (
        "Underground-sump pressure jobs should allow Pressure Booster candidates."
    )

    print("Ground-floor below-grade source rules: PASS")


if __name__ == "__main__":
    verify_worked_example()
    print()
    verify_relaxed_ground_lift_rules()
