"""Smoke tests for the Framework v1.2 pump-selection package."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from rules import evaluate
from scoring import filter_skus, score_skus
from vector import MATRIX, build_vector

BASE_DIR = Path(__file__).parent
CATALOGUE_CANDIDATES = [
    BASE_DIR / "FINAL_MASTER_DATASHEET_final.xlsx",
    BASE_DIR / "MASTER DATASHEET_final_final copy(15).xlsx",
]


def catalogue_path() -> Path:
    for path in CATALOGUE_CANDIDATES:
        if path.exists():
            return path
    raise FileNotFoundError("Could not find the master catalogue next to _verify.py.")


def load_catalogue() -> pd.DataFrame:
    return pd.read_excel(catalogue_path(), sheet_name="Master Data")


def assert_close(actual: float, expected: float, tol: float = 0.75):
    assert abs(actual - expected) <= tol, f"Expected {expected}, got {actual}"


def verify_framework_worked_example() -> None:
    ans = {
        "setting": "large_commercial",
        "job": "lift_and_store",
        "source": "borewell",
        "c0_destination": "overhead_tank",
        "lift": 15,
        "demand": "vol_50000",
        "c1_casing": "casing_6in",
        "c2_depth_m": 90,
        "c8_duty": "heavy",
        "c9_min_v": 380,
        "c9_max_v": 430,
    }
    assert not [e for e in evaluate(ans) if e[1] == "hard"], evaluate(ans)
    vec = build_vector(ans)
    assert vec["allowed_pump_types"] == ["Borewell Pump"]
    assert_close(vec["required_min_head"], 155)
    assert_close(vec["typical_head"], 171)
    assert vec["required_min_flow"] == 8000
    assert vec["typical_flow"] == 12000
    assert vec["special"]["c9_variant"] == "three_phase_range"

    df = load_catalogue()
    survivors, trace = filter_skus(df, vec)
    scored = score_skus(survivors, vec)
    assert len(scored) > 0, "Worked example should return catalogue candidates."
    assert trace[0]["rows_left"] == 4056, "Master catalogue row count should match the supplied sheet."
    assert trace[1]["rows_left"] == 4025, "Usable head/flow row count should match the supplied sheet."
    print("Worked example vector and filtering: PASS")
    print(scored[["Brand", "SKU", "Type", "score"]].head(5).to_string(index=False))


def verify_open_ground_7m_rule() -> None:
    shallow = {
        "setting": "farm",
        "job": "boost_pressure",
        "source": "open_ground",
        "c0_destination": "irrigation",
        "c3g_depth_m": 7,
        "demand": "vol_50000",
        "c5a_pressure": "farm_sprinkler",
        "c4_outlets": "farm_sprinkler_13_25",
        "c5_usage": "heavy",
        "water_scarce": True,
        "c7_phase": "Three",
        "c8_duty": "heavy",
        "c9_min_v": 360,
        "c9_max_v": 430,
    }
    deep = dict(shallow, c3g_depth_m=8, water_scarce=False)
    v1 = build_vector(shallow)
    v2 = build_vector(deep)
    assert v1["allowed_pump_types"] == ["Self-Priming Pump"]
    assert v1["special"]["suction_lift_required"] == 7
    assert v1["special"]["water_scarce"] is True
    assert v1["components"]["source_depth_add_m"] == 0
    assert v2["allowed_pump_types"] == ["Openwell Pump"]
    assert v2["components"]["source_depth_add_m"] == 8
    assert "water_scarce" not in v2["special"]
    print("Open-ground-water 7 m rule and water-scarcity advisory: PASS")


def verify_farm_pressure_cluster_order_values() -> None:
    ans = {
        "setting": "farm",
        "job": "boost_pressure",
        "source": "borewell",
        "c0_destination": "irrigation",
        "c2_depth_m": 30,
        "c1_casing": "casing_6in",
        "demand": "vol_10000",
        "c5a_pressure": "farm_drip",
        "c4_outlets": "farm_drip_4_8",
        "c5_usage": "moderate",
        "c7_phase": "Three",
        "c8_duty": "moderate",
        "c9_min_v": 360,
        "c9_max_v": 430,
    }
    assert not [e for e in evaluate(ans) if e[1] == "hard"], evaluate(ans)
    vec = build_vector(ans)
    assert vec["components"]["outlet_flow_lph"] == 7200  # 14,400 × 0.5
    print("Farm C5a-first tailored fixture flow: PASS")


def verify_drain_two_slider_sizing() -> None:
    ans = {
        "setting": "home",
        "job": "drain_sewage",
        "source": "sewage_pit",
        "drain_quantity_l": 1000,
        "drain_time_h": 0.5,
        "c6_quality": "heavy_sewage",
        "c9_voltage_band": "single_normal_200_240",
    }
    assert not [e for e in evaluate(ans) if e[1] == "hard"], evaluate(ans)
    vec = build_vector(ans)
    assert vec["allowed_pump_types"] == ["Sewage Pump"]
    assert vec["special"]["cutter_required"] == "with cutter"
    assert vec["required_min_flow"] == 2000
    assert vec["typical_flow"] == 3000
    print("Drain sewage/water two-slider flow and cutter logic: PASS")


def verify_matrix_not_empty() -> None:
    assert ("light_industry", "lift_and_store", "borewell", "overhead_tank") in MATRIX
    assert ("farm", "boost_pressure", "open_ground", "irrigation") in MATRIX
    assert ("home", "drain_sewage", "sewage_pit", None) in MATRIX
    print(f"Matrix contains {len(MATRIX)} expanded tuples: PASS")


def main() -> None:
    verify_matrix_not_empty()
    verify_framework_worked_example()
    verify_open_ground_7m_rule()
    verify_farm_pressure_cluster_order_values()
    verify_drain_two_slider_sizing()


if __name__ == "__main__":
    main()
