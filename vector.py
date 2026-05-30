"""
vector.py — Requirement-vector builder aligned to Pump Use-Case Framework v1.1.

This module is the compact contract between the Streamlit questionnaire and
scoring.py. It implements the v1.1 control matrix, conditional lift, metre-based
source-depth sliders, the 7 m open-ground-water rule, consolidated head formula,
setting-specific demand bands, Boost-pressure C4/C5/C5a logic, C7 phase defaults,
C8 duty-cycle run-times, and the corrected C9 voltage-envelope model.
"""

from __future__ import annotations

from typing import Iterable

# ---------------------------------------------------------------------------
# Canonical keys and customer labels
# ---------------------------------------------------------------------------

SETTINGS = {
    "home": "Home",
    "farm": "Farm / agriculture",
    "shop_small_comm": "Shop / office / small commercial",
    "large_commercial": "Large commercial or institutional",
    "light_industry": "Light industry / warehouse / construction site",
}

JOBS = {
    "lift_and_store": "Lift and store",
    "boost_pressure": "Boost pressure",
    "drain_sewage": "Drain sewage / water",
}

SOURCES = {
    "borewell": "Borewell",
    "open_well": "Open well or pond",
    "open_ground": "Open ground water (canal, river, farm channel)",
    "underground_sump": "Underground sump or storage tank",
    "overhead_tank": "Overhead tank",
    "municipal": "Municipal / shared piped water supply line",
    "sewage_pit": "Sewage or drainage pit",
}

DESTINATIONS = {
    "overhead_tank": "Overhead tank",
    "ground_sump": "Ground-level storage tank or sump",
    "direct_pipes": "Direct to building pipes",
    "irrigation": "Irrigation lines / open field / livestock",
    "industrial_process": "Industrial process or treatment system",
}

PUMP_TYPES = {
    "borewell": "Borewell Pump",
    "openwell": "Openwell Pump",
    "self_priming": "Self-Priming Pump",
    "pressure_booster": "Pressure Booster Pump",
    "hydropneumatic": "Hydropneumatic Pump",
    "sewage": "Sewage Pump",
}

# ---------------------------------------------------------------------------
# Matrix: authoritative Setting × Job × Source × Destination gate
# ---------------------------------------------------------------------------

MATRIX: dict[tuple[str, str, str, str | None], list[str]] = {}


def _add(
    setting: str,
    job: str,
    source: str,
    destinations: Iterable[str | None],
    types: Iterable[str],
) -> None:
    catalogue_types = [PUMP_TYPES[t] for t in types]
    for destination in destinations:
        MATRIX[(setting, job, source, destination)] = catalogue_types


# 4.1 Lift and store. "Storage" means both overhead tank and ground-level sump.
_storage = ["overhead_tank", "ground_sump"]

_add("home", "lift_and_store", "borewell", _storage, ["borewell"])
_add("home", "lift_and_store", "open_well", _storage, ["openwell"])
_add("home", "lift_and_store", "underground_sump", _storage, ["self_priming", "openwell"])
_add("home", "lift_and_store", "municipal", ["ground_sump"], ["self_priming"])

_add("farm", "lift_and_store", "borewell", _storage, ["borewell"])
_add("farm", "lift_and_store", "open_well", _storage, ["openwell"])
_add("farm", "lift_and_store", "open_ground", _storage, ["self_priming", "openwell"])
_add("farm", "lift_and_store", "underground_sump", _storage, ["self_priming", "openwell"])

_add("shop_small_comm", "lift_and_store", "borewell", _storage, ["borewell"])
_add("shop_small_comm", "lift_and_store", "open_well", _storage, ["openwell"])
_add("shop_small_comm", "lift_and_store", "open_ground", ["ground_sump"], ["self_priming", "openwell"])
_add("shop_small_comm", "lift_and_store", "underground_sump", ["overhead_tank"], ["self_priming", "openwell"])
_add("shop_small_comm", "lift_and_store", "municipal", ["ground_sump"], ["self_priming"])

_add("large_commercial", "lift_and_store", "borewell", _storage, ["borewell"])
_add("large_commercial", "lift_and_store", "underground_sump", _storage, ["self_priming", "openwell"])
_add("large_commercial", "lift_and_store", "municipal", ["ground_sump"], ["self_priming"])

_add("light_industry", "lift_and_store", "borewell", _storage, ["borewell"])
_add("light_industry", "lift_and_store", "underground_sump", _storage, ["self_priming", "openwell"])
_add("light_industry", "lift_and_store", "municipal", ["ground_sump"], ["self_priming"])

# 4.2 Boost pressure.
_add("home", "boost_pressure", "underground_sump", ["direct_pipes"], ["hydropneumatic", "pressure_booster"])
_add("home", "boost_pressure", "overhead_tank", ["direct_pipes"], ["hydropneumatic", "pressure_booster"])

_add("farm", "boost_pressure", "borewell", ["irrigation"], ["borewell"])
_add("farm", "boost_pressure", "open_well", ["irrigation"], ["openwell"])
_add("farm", "boost_pressure", "open_ground", ["irrigation"], ["self_priming", "openwell"])
_add("farm", "boost_pressure", "underground_sump", ["irrigation"], ["openwell", "self_priming", "pressure_booster"])

_add("shop_small_comm", "boost_pressure", "overhead_tank", ["direct_pipes"], ["hydropneumatic", "pressure_booster"])
_add("shop_small_comm", "boost_pressure", "underground_sump", ["direct_pipes"], ["hydropneumatic", "pressure_booster"])

_add("large_commercial", "boost_pressure", "overhead_tank", ["direct_pipes"], ["hydropneumatic", "pressure_booster"])
_add("large_commercial", "boost_pressure", "underground_sump", ["direct_pipes"], ["hydropneumatic", "pressure_booster"])
_add("large_commercial", "boost_pressure", "overhead_tank", ["industrial_process"], ["hydropneumatic", "pressure_booster"])
_add("large_commercial", "boost_pressure", "underground_sump", ["industrial_process"], ["hydropneumatic", "pressure_booster"])

_add("light_industry", "boost_pressure", "overhead_tank", ["direct_pipes"], ["hydropneumatic", "pressure_booster"])
_add("light_industry", "boost_pressure", "underground_sump", ["direct_pipes"], ["hydropneumatic", "pressure_booster"])
_add("light_industry", "boost_pressure", "borewell", ["industrial_process"], ["borewell"])
_add("light_industry", "boost_pressure", "underground_sump", ["industrial_process"], ["hydropneumatic", "pressure_booster"])

# 4.3 Drain sewage / water. Source is auto-resolved to sewage/drainage pit.
for _setting in SETTINGS:
    _add(_setting, "drain_sewage", "sewage_pit", [None], ["sewage"])

# ---------------------------------------------------------------------------
# Engine lookup tables
# ---------------------------------------------------------------------------

SETTING_DEFAULTS = {
    "home": {"phase": "Single", "hp_cap": 3},
    "farm": {"phase": "Three", "hp_cap": None},
    "shop_small_comm": {"phase": "Single", "hp_cap": 3},
    "large_commercial": {"phase": "Three", "hp_cap": None},
    "light_industry": {"phase": "Three", "hp_cap": None},
}

LIFT_HEAD_M = {
    "ground": 0,
    "floor_1": 3,
    "floor_2": 6,
    "floor_3": 9,
    "floor_4": 12,
    "floors_5_10": 30,
    "floors_11_15": 45,
    "floors_16_25": 75,
    "floors_26_40": 120,
    "floors_41_60": 180,
    "floors_above_60": 180,
}

# Engine volume band -> representative daily litres, default run hours,
# minimum flow floor, typical flow.
DEMAND_FLOW = {
    "vol_200": (200, 2, 500, 800),
    "vol_800": (800, 2, 800, 1200),
    "vol_2000": (2000, 3, 1000, 1500),
    "vol_5000": (5000, 3, 2500, 3500),
    "vol_10000": (10000, 4, 2500, 3500),
    "vol_50000": (30000, 6, 8000, 12000),
    "vol_200000": (120000, 8, 25000, 40000),
    "vol_above_200000": (300000, 10, 50000, 80000),
}

DRAIN_FLOW = {
    "trickle": (6000, 10000),
    "routine_small": (12000, 18000),
    "steady_moderate": (24000, 36000),
    "heavy_flow": (60000, 90000),
    "very_heavy": (120000, 180000),
    "industrial_large": (300000, 300000),
}

C8_HOURS = {
    "moderate": 4,
    "heavy": 9,
    "continuous": 14,
}

C1_VCODES = {
    "casing_4in": ["V3", "V3.5", "V4"],
    "casing_6in": ["V3", "V3.5", "V4", "V5", "V6"],
    "casing_8in": ["V6", "V7", "V8"],
    "casing_10in": ["V8", "V9"],
    "casing_12in_plus": ["V12", "V13", "V14", "V15", "V16", "V17", "V18", "V19", "V20"],
}

OUTLET_PEAKS = {
    "home_shop": {
        "1_4": 2400,
        "5_12": 7200,
        "13_20": 12000,
        "21_35": 21000,
        "36_75": 45000,
        "76_150": 90000,
        "above_150": 150000,
    },
    "farm_industry": {
        "1_4": 3600,
        "5_12": 10800,
        "13_20": 18000,
        "21_35": 31500,
        "36_75": 67500,
        "76_150": 135000,
        "above_150": 200000,
    },
}

USAGE_MULT = {
    "light": 0.3,
    "moderate": 0.5,
    "heavy": 0.7,
    "constant_peak": 1.0,
}

C5A_HEAD_ADD = {
    "home_standard": 0,
    "home_premium": 20,
    "shop_standard": 0,
    "shop_premium": 20,
    "large_comm_standard": 0,
    "large_comm_premium": 20,
    "farm_flood": 5,
    "farm_drip": 12,
    "farm_sprinkler": 20,
    "farm_rain_gun": 50,
    "industry_standard": 0,
    "industry_light_wash": 18,
    "industry_routine_wash": 30,
    "industry_heavy_jetting": 45,
}

C5A_ALLOWED_BY_SETTING = {
    "home": {"home_standard", "home_premium"},
    "shop_small_comm": {"shop_standard", "shop_premium"},
    "large_commercial": {"large_comm_standard", "large_comm_premium"},
    "farm": {"farm_flood", "farm_drip", "farm_sprinkler", "farm_rain_gun"},
    "light_industry": {"industry_standard", "industry_light_wash", "industry_routine_wash", "industry_heavy_jetting"},
}

C6_RULES = {
    "clean_water": {"cutter": "non-cutter"},
    "lightly_soiled": {"cutter": "non-cutter"},
    "solids_waste": {"cutter": "with cutter"},
    "heavy_sewage": {"cutter": "with cutter"},
}

LOW_C9_BAND = "single_low_under_200"
NORMAL_C9_BAND = "single_normal_200_240"

THREE_MIN_VALUES = list(range(340, 411, 10))
THREE_MAX_VALUES = list(range(360, 441, 10))
FARM_SINGLE_MIN_VALUES = list(range(140, 221, 10))
FARM_SINGLE_MAX_VALUES = list(range(190, 241, 10))

# ---------------------------------------------------------------------------
# Matrix and journey helpers
# ---------------------------------------------------------------------------


def matrix_key(ans: dict) -> tuple[str, str, str, str | None] | None:
    setting = ans.get("setting")
    job = ans.get("job")
    source = ans.get("source") or ("sewage_pit" if job == "drain_sewage" else None)
    destination = None if job == "drain_sewage" else ans.get("c0_destination")
    if not (setting and job and source and (job == "drain_sewage" or destination)):
        return None
    return setting, job, source, destination


def is_matrix_enabled(ans: dict) -> bool:
    key = matrix_key(ans)
    return bool(key and key in MATRIX)


def available_jobs(setting: str | None) -> list[str]:
    if not setting:
        return []
    return sorted({job for s, job, _src, _dest in MATRIX if s == setting}, key=list(JOBS).index)


def available_sources(setting: str | None, job: str | None) -> list[str]:
    if not setting or not job:
        return []
    if job == "drain_sewage":
        return ["sewage_pit"]
    order = list(SOURCES)
    return sorted({src for s, j, src, _dest in MATRIX if s == setting and j == job}, key=order.index)


def available_destinations(setting: str | None, job: str | None, source: str | None) -> list[str]:
    if not setting or not job or not source or job == "drain_sewage":
        return []
    order = list(DESTINATIONS)
    return sorted(
        {dest for s, j, src, dest in MATRIX if s == setting and j == job and src == source and dest},
        key=order.index,
    )


def lift_triggered(ans: dict) -> bool:
    job = ans.get("job")
    dest = ans.get("c0_destination")
    if job == "lift_and_store":
        return dest == "overhead_tank"
    if job == "boost_pressure":
        return dest in {"direct_pipes", "industrial_process"}
    return False


def construction_drain_lift_triggered(ans: dict) -> bool:
    return ans.get("job") == "drain_sewage" and ans.get("setting") == "light_industry"


def source_depth_field(source: str | None) -> str | None:
    return {
        "borewell": "c2_depth_m",
        "open_well": "c3_depth_m",
        "open_ground": "c3g_depth_m",
    }.get(source or "")


def daily_volume(ans: dict) -> float | None:
    demand = ans.get("demand")
    if not demand:
        return None
    return DEMAND_FLOW[demand][0]


def c8_triggered(ans: dict) -> bool:
    setting = ans.get("setting")
    if not setting:
        return False
    if setting in {"farm", "large_commercial", "light_industry"}:
        return True
    dv = daily_volume(ans)
    return bool(dv is not None and dv >= 10000)


def default_phase(setting: str) -> str:
    return SETTING_DEFAULTS[setting]["phase"]


def _lift_rank(lift: str | None) -> int:
    order = list(LIFT_HEAD_M)
    return order.index(lift) if lift in order else -1


def needs_phase_confirm(ans: dict) -> bool:
    setting = ans.get("setting")
    if not setting:
        return False
    if setting in {"farm", "shop_small_comm"}:
        return True
    if setting == "home":
        if _lift_rank(ans.get("lift")) >= _lift_rank("floors_5_10"):
            return True
        depth = float(ans.get("c2_depth_m") or 0)
        if depth >= 90:
            return True
        dv = daily_volume(ans)
        return bool(dv is not None and dv >= 10000)
    return False


def final_phase(ans: dict) -> str | None:
    if not ans.get("setting"):
        return None
    return ans.get("c7_phase") or default_phase(ans["setting"])


def c9_variant(setting: str, phase: str) -> str:
    if setting in {"home", "shop_small_comm"} and phase == "Single":
        return "single_band"
    if setting == "farm" and phase == "Single":
        return "farm_single_range"
    return "three_phase_range"


def phase_allowed_values(phase: str) -> set[str]:
    return {"Single", "Both"} if phase == "Single" else {"Three", "Both"}


def allowed_c9_min_values(setting: str, phase: str) -> list[int]:
    variant = c9_variant(setting, phase)
    if variant == "farm_single_range":
        return FARM_SINGLE_MIN_VALUES
    if variant == "three_phase_range":
        return THREE_MIN_VALUES
    return []


def allowed_c9_max_values(setting: str, phase: str, min_v: int | None = None) -> list[int]:
    variant = c9_variant(setting, phase)
    values = FARM_SINGLE_MAX_VALUES if variant == "farm_single_range" else THREE_MAX_VALUES
    if variant == "single_band":
        return []
    if min_v is None:
        return values
    return [v for v in values if v > min_v]


def _round_m(x: float) -> float:
    return round(float(x), 2)


# ---------------------------------------------------------------------------
# Requirement-vector builder
# ---------------------------------------------------------------------------


def build_vector(ans: dict) -> dict:
    """Build the v1.1 requirement vector consumed by scoring.py.

    The input answer dictionary is expected to be complete enough for matching.
    Invalid or incomplete matrix combinations return an out-of-scope vector with
    an empty allowed-type list, so the caller gets no recommendations rather than
    silently guessing.
    """

    ans = dict(ans)
    if ans.get("job") == "drain_sewage":
        ans["source"] = "sewage_pit"
        ans["c0_destination"] = None

    key = matrix_key(ans)
    special: dict = {}
    warnings: list[str] = []

    if key not in MATRIX:
        return {
            "allowed_pump_types": [],
            "required_min_head": 0,
            "typical_head": 0,
            "required_min_flow": 0,
            "typical_flow": 0,
            "daily_volume": None,
            "run_hours": None,
            "allowed_phase": set(),
            "hp_cap": None,
            "final_phase": None,
            "special": {"out_of_scope": "matrix_gate"},
            "warnings": ["matrix_gate_failed"],
            "components": {},
        }

    allowed_types = list(MATRIX[key])
    source = ans.get("source")
    job = ans.get("job")
    setting = ans.get("setting")

    lift_m = 0.0
    if lift_triggered(ans):
        lift_m = float(LIFT_HEAD_M.get(ans.get("lift"), 0))
    elif construction_drain_lift_triggered(ans):
        lift_m = float(ans.get("construction_lift_m") or 0)
        if lift_m <= 3:
            lift_m = 0.0

    source_depth_add_m = 0.0
    sump_allowance_m = 3.0 if source == "underground_sump" else 0.0

    if source == "borewell":
        source_depth_add_m = float(ans.get("c2_depth_m") or 0)
        if ans.get("c1_casing"):
            special["borewell_vcodes"] = C1_VCODES.get(ans["c1_casing"], [])
    elif source == "open_well":
        source_depth_add_m = float(ans.get("c3_depth_m") or 0)
    elif source == "open_ground":
        depth = float(ans.get("c3g_depth_m") or 0)
        special["open_ground_depth_m"] = depth
        if depth <= 7:
            allowed_types = [PUMP_TYPES["self_priming"]]
            special["suction_lift_required"] = depth
            special["open_ground_rule"] = "surface_suction_le_7m"
            if ans.get("water_scarce"):
                special["water_scarce"] = True
                warnings.append("water_scarcity_slow_speed_advisory")
        else:
            allowed_types = [PUMP_TYPES["openwell"]]
            source_depth_add_m = depth
            special["open_ground_rule"] = "openwell_depth_gt_7m"

    c5a_add_m = 0.0
    if job == "boost_pressure" and ans.get("c5a_pressure"):
        c5a_add_m = float(C5A_HEAD_ADD.get(ans["c5a_pressure"], 0))

    static_head_m = lift_m + source_depth_add_m + sump_allowance_m
    friction_m = max(5.0, 0.15 * static_head_m)
    required_min_head = static_head_m + c5a_add_m + friction_m
    typical_head = max(required_min_head * 1.1, required_min_head + 5.0)

    rep_daily = None
    run_hours = None
    required_min_flow = 0.0
    typical_flow = 0.0
    demand_based_flow = 0.0
    outlet_flow = 0.0
    c5a_required_floor = 0.0
    c5a_typical_floor = 0.0

    if job == "drain_sewage":
        required_min_flow, typical_flow = DRAIN_FLOW[ans["drain_rate"]]
        if ans.get("c6_quality"):
            special["cutter_required"] = C6_RULES[ans["c6_quality"]]["cutter"]
        if ans.get("drain_rate") == "industrial_large":
            warnings.append("custom_engineering_required")
    else:
        rep_daily, default_hours, min_floor, band_typical = DEMAND_FLOW[ans["demand"]]
        run_hours = C8_HOURS.get(ans.get("c8_duty"), default_hours)
        demand_based_flow = max(rep_daily / run_hours, min_floor)
        required_min_flow = demand_based_flow
        typical_flow = max(float(band_typical), required_min_flow)

        if job == "boost_pressure":
            peak_family = "home_shop" if setting in {"home", "shop_small_comm"} else "farm_industry"
            if ans.get("c4_outlets") and ans.get("c5_usage"):
                outlet_peak = OUTLET_PEAKS[peak_family][ans["c4_outlets"]]
                outlet_flow = outlet_peak * USAGE_MULT[ans["c5_usage"]]

            if (
                setting == "home"
                and ans.get("c5a_pressure") == "home_premium"
                and ans.get("c4_outlets") in {"1_4", "5_12"}
            ):
                c5a_required_floor = 3000.0
                c5a_typical_floor = 3500.0
                warnings.append("home_premium_flow_floor")

            if setting == "farm" and ans.get("c5a_pressure") == "farm_rain_gun" and (rep_daily or 0) < 10000:
                warnings.append("rain_gun_high_pressure_small_demand")
            if setting == "light_industry" and ans.get("c5a_pressure") == "industry_heavy_jetting" and (rep_daily or 0) < 5000:
                warnings.append("heavy_jetting_small_demand")

            required_min_flow = max(demand_based_flow, outlet_flow, c5a_required_floor)
            typical_flow = max(float(band_typical), outlet_flow, c5a_typical_floor, required_min_flow)

    phase = final_phase(ans)
    allowed_phase = phase_allowed_values(phase) if phase else set()
    hp_cap = SETTING_DEFAULTS[setting]["hp_cap"]

    variant = c9_variant(setting, phase) if phase else None
    if variant == "single_band":
        special["c9_variant"] = "single_band"
        special["c9_band"] = ans.get("c9_voltage_band")
    elif variant == "farm_single_range":
        special["c9_variant"] = "farm_single_range"
        special["c9_min_v"] = ans.get("c9_min_v")
        special["c9_max_v"] = ans.get("c9_max_v")
    elif variant == "three_phase_range":
        special["c9_variant"] = "three_phase_range"
        special["c9_min_v"] = ans.get("c9_min_v")
        special["c9_max_v"] = ans.get("c9_max_v")

    if source == "municipal":
        warnings.append("municipal_marginal_pressure")
        special["municipal_path"] = True

    if ans.get("lift") == "floors_16_25":
        warnings.append("staged_pumping_recommended")
    elif ans.get("lift") == "floors_26_40":
        warnings.append("multi_zone_booster_required")
    elif ans.get("lift") == "floors_41_60":
        warnings.append("consultant_review_recommended")
    elif ans.get("lift") == "floors_above_60":
        warnings.append("custom_engineering_required")

    return {
        "allowed_pump_types": allowed_types,
        "required_min_head": _round_m(required_min_head),
        "typical_head": _round_m(typical_head),
        "required_min_flow": _round_m(required_min_flow),
        "typical_flow": _round_m(typical_flow),
        "daily_volume": rep_daily,
        "run_hours": run_hours,
        "allowed_phase": allowed_phase,
        "hp_cap": hp_cap,
        "final_phase": phase,
        "special": special,
        "warnings": list(dict.fromkeys(warnings)),
        "components": {
            "lift_m": _round_m(lift_m),
            "source_depth_add_m": _round_m(source_depth_add_m),
            "sump_allowance_m": _round_m(sump_allowance_m),
            "static_head_m": _round_m(static_head_m),
            "c5a_head_add_m": _round_m(c5a_add_m),
            "friction_m": _round_m(friction_m),
            "demand_based_flow_lph": _round_m(demand_based_flow),
            "outlet_flow_lph": _round_m(outlet_flow),
            "c5a_required_floor_lph": _round_m(c5a_required_floor),
            "c5a_typical_floor_lph": _round_m(c5a_typical_floor),
        },
    }
