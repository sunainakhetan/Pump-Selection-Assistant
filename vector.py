"""
vector.py — Requirement-vector builder aligned to Pump Use-Case Framework v0.6.

The vector is the single compact contract consumed by scoring.py. It uses the
new setting-specific demand bands, C5a pressure add-ons, C7 default/confirm
phase logic, and the four-variant C9 voltage model.
"""

# ---------------------------------------------------------------------------
# Core lookup tables
# ---------------------------------------------------------------------------

JOB_TYPES = {
    "lift_and_store": ["Self-Priming Pump", "Openwell Pump", "Borewell Pump"],
    "lift_and_pressurise_directly": [
        "Self-Priming Pump",
        "Openwell Pump",
        "Borewell Pump",
        "Pressure Booster Pump",
        "Hydropneumatic Pump",
    ],
    "boost_pressure": ["Pressure Booster Pump", "Hydropneumatic Pump"],
    "drain_water": ["Self-Priming Pump", "Sewage Pump"],
    "pump_sewage": ["Sewage Pump"],
}

SOURCE_TYPES = {
    "borewell": {
        "types": ["Borewell Pump"],
        "suction_required": None,
    },
    "open_well": {
        "types": ["Openwell Pump", "Self-Priming Pump", "Borewell Pump"],
        "suction_required": 6,
    },
    "underground_sump": {
        "types": [
            "Self-Priming Pump",
            "Openwell Pump",
            "Pressure Booster Pump",
            "Hydropneumatic Pump",
        ],
        "suction_required": 6,
    },
    "overhead_tank": {
        "types": ["Pressure Booster Pump", "Hydropneumatic Pump"],
        "suction_required": 0,
    },
    "municipal": {
        "types": ["Pressure Booster Pump", "Hydropneumatic Pump"],
        "suction_required": None,
    },
    "sewage_pit": {
        "types": ["Sewage Pump"],
        "suction_required": None,
    },
    "open_ground": {
        "types": ["Openwell Pump", "Self-Priming Pump"],
        "suction_required": 6,
    },
}

LIFT_HEAD = {
    "ground": (0, 5),
    "floor_1": (6, 12),
    "floor_2": (9, 15),
    "floor_3": (12, 18),
    "floor_4": (15, 22),
    "floors_5_10": (30, 40),
    "floors_11_15": (45, 55),
    "floors_16_25": (75, 85),
    "floors_26_40": (120, 135),
    "floors_41_60": (180, 200),
    "floors_above_60": (180, 220),
}

# Engine volume band -> representative daily litres, default run hours,
# minimum flow, typical flow.
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

SETTING_DEFAULTS = {
    "home": ("Single", 3),
    "farm": ("Three", None),
    "shop_small_comm": ("Single", 3),
    "large_commercial": ("Three", None),
    "light_industry": ("Three", None),
}

PER_OUTLET_FLOW = {
    "home": 600,
    "shop_small_comm": 600,
    "farm": 900,
    "large_commercial": 900,
    "light_industry": 900,
}

USAGE_MULT = {
    "light": 0.3,
    "moderate": 0.5,
    "heavy": 0.7,
    "constant_peak": 1.0,
}

C8_HOURS = {
    "moderate": 4,
    "heavy": 9,
    "continuous": 14,
}

# Revised v0.6 C1 V-code eligibility. V2.5 is treated as 4-inch class.
C1_VCODES = {
    "casing_4in": ["V2.5", "V3", "V3.5", "V4"],
    "casing_6in": ["V3", "V3.5", "V4", "V5", "V6"],
    "casing_8in": ["V6", "V7", "V8"],
    "casing_10in": ["V8", "V9"],
    "casing_12in_plus": ["V10", "V11", "V12", "V13", "V14", "V15", "V16"],
}

C2_HEAD_ADD = {
    "under_50ft": 15,
    "50_100ft": 30,
    "100_200ft": 60,
    "200_300ft": 90,
    "300_450ft": 135,
    "450_600ft": 180,
    "600_800ft": 245,
    "800_1000ft": 305,
    "above_1000ft": 350,
}

C3_HEAD_ADD = {
    "shallow_under_30ft": (9, ["Self-Priming Pump", "Openwell Pump"]),
    "medium_30_60ft": (18, ["Openwell Pump", "Self-Priming Pump"]),
    "deep_above_60ft": (25, ["Openwell Pump", "Borewell Pump"]),
}

# Underground sump/storage has no measured C2/C3 source-depth answer, but it
# still sits below floor level. The framework therefore adds a fixed shallow
# below-grade allowance when Source = underground sump/storage.
SUMP_LIFT_HEAD_ADD = (8, 12)  # (required minimum head, typical head)

C5A_HEAD_ADD = {
    "home_standard": 0,
    "home_premium": 20,
    "shop_standard": 0,
    "shop_premium": 20,
    "large_comm_standard": 0,
    "large_comm_premium": 20,
    "farm_flood": 5,
    "farm_drip": 12,
    "farm_sprinkler": 30,
    "farm_rain_gun": 50,
    "industry_standard": 0,
    "industry_light_wash": 18,
    "industry_routine_wash": 30,
    "industry_heavy_jetting": 45,
}

C6_RULES = {
    "clean_water": {
        "types": ["Self-Priming Pump", "Sewage Pump"],
        "cutter": None,
        "out_of_scope": False,
    },
    "lightly_soiled": {
        "types": ["Self-Priming Pump", "Sewage Pump"],
        "cutter": None,
        "out_of_scope": False,
        "self_priming_rpm_max": 1500,
    },
    "solids_waste": {
        "types": ["Sewage Pump"],
        "cutter": "with cutter",
        "out_of_scope": False,
    },
    "heavy_sewage": {
        "types": ["Sewage Pump"],
        "cutter": "with cutter",
        "out_of_scope": False,
    },
    "industrial_effluent": {
        "types": [],
        "cutter": None,
        "out_of_scope": True,
    },
}

LOW_C9_BAND = "single_low_under_200"
NORMAL_C9_BAND = "single_normal_200_240"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _intersect(a, b):
    return [x for x in a if x in b]


def daily_volume(ans: dict) -> float:
    return DEMAND_FLOW[ans["demand"]][0]


def demand_default_run_hours(ans: dict) -> float:
    return DEMAND_FLOW[ans["demand"]][1]


def c8_triggered(ans: dict) -> bool:
    if not ans.get("setting") or not ans.get("demand"):
        return False

    return (
        ans["setting"] in {"farm", "large_commercial", "light_industry"}
        or daily_volume(ans) >= 10000
    )


def needs_phase_confirm(ans: dict) -> bool:
    if not ans.get("setting"):
        return False

    if ans["setting"] in {"shop_small_comm", "farm"}:
        return True

    if ans["setting"] == "home":
        return (
            ans.get("lift")
            in {
                "floors_5_10",
                "floors_11_15",
                "floors_16_25",
                "floors_26_40",
                "floors_41_60",
                "floors_above_60",
            }
            or (ans.get("demand") and daily_volume(ans) >= 10000)
            or ans.get("c2_depth")
            in {
                "300_450ft",
                "450_600ft",
                "600_800ft",
                "800_1000ft",
                "above_1000ft",
            }
        )

    return False


def default_phase(setting: str) -> str:
    return SETTING_DEFAULTS[setting][0]


def c9_variant(setting: str, phase: str) -> str:
    if setting in {"home", "shop_small_comm"} and phase == "Single":
        return "single_band"

    if setting == "farm" and phase == "Single":
        return "farm_single_range"

    return "three_phase_range"


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

def build_vector(ans: dict) -> dict:
    job_types = JOB_TYPES[ans["job"]]
    src_types = SOURCE_TYPES[ans["source"]]["types"]
    allowed_types = _intersect(job_types, src_types)

    if ans.get("c3_well_depth"):
        _, refined = C3_HEAD_ADD[ans["c3_well_depth"]]
        allowed_types = _intersect(allowed_types, refined)

    if ans.get("c6_quality"):
        rule = C6_RULES[ans["c6_quality"]]
        allowed_types = [] if rule["out_of_scope"] else _intersect(allowed_types, rule["types"])

    lift_min, lift_typ = LIFT_HEAD[ans["lift"]]
    head_add_min = 0
    head_add_typ = 0

    if ans.get("c2_depth"):
        add = C2_HEAD_ADD[ans["c2_depth"]]
        head_add_min += add
        head_add_typ += add

    if ans.get("c3_well_depth"):
        add = C3_HEAD_ADD[ans["c3_well_depth"]][0]
        head_add_min += add
        head_add_typ += add

    if ans.get("source") == "underground_sump":
        sump_min, sump_typ = SUMP_LIFT_HEAD_ADD
        head_add_min += sump_min
        head_add_typ += sump_typ

    if ans.get("c5a_pressure"):
        add = C5A_HEAD_ADD[ans["c5a_pressure"]]
        head_add_min += add
        head_add_typ += add

    required_min_head = lift_min + head_add_min
    typical_head = lift_typ + head_add_typ

    rep_daily, default_hours, demand_min_flow, demand_typ_flow = DEMAND_FLOW[ans["demand"]]
    run_hours = C8_HOURS[ans["c8_duty"]] if ans.get("c8_duty") else default_hours
    demand_based_flow = rep_daily / run_hours

    outlet_based_flow = 0
    if ans.get("c4_outlets_count") and ans.get("c5_usage"):
        outlet_based_flow = (
            ans["c4_outlets_count"]
            * PER_OUTLET_FLOW[ans["setting"]]
            * USAGE_MULT[ans["c5_usage"]]
        )

    c5a_required_floor = 0
    c5a_typical_floor = 0

    if (
        ans.get("setting") == "home"
        and ans.get("c5a_pressure") == "home_premium"
        and ans.get("c4_outlets") in {"1_4", "5_12"}
    ):
        c5a_required_floor = 3000
        c5a_typical_floor = 3500

    required_min_flow = max(
        demand_min_flow,
        demand_based_flow,
        outlet_based_flow,
        c5a_required_floor,
    )

    typical_flow = max(
        demand_typ_flow,
        required_min_flow * 1.15,
        c5a_typical_floor,
    )

    default_phase_value, hp_cap = SETTING_DEFAULTS[ans["setting"]]
    final_phase = ans.get("c7_phase") or default_phase_value
    allowed_phase = {"Single", "Both"} if final_phase == "Single" else {"Three", "Both"}

    special = {}

    if ans["source"] == "borewell" and ans.get("c1_casing"):
        special["borewell_vcodes"] = C1_VCODES[ans["c1_casing"]]

        if ans["c1_casing"] == "casing_4in":
            special["prefer_slim_v3"] = True

    suction_required = SOURCE_TYPES[ans["source"]]["suction_required"]
    if suction_required is not None:
        special["suction_lift_required"] = suction_required

    if ans.get("c6_quality"):
        rule = C6_RULES[ans["c6_quality"]]

        if rule.get("cutter"):
            special["cutter_required"] = rule["cutter"]

        if rule.get("self_priming_rpm_max"):
            special["self_priming_rpm_max"] = rule["self_priming_rpm_max"]

        if rule.get("out_of_scope"):
            special["out_of_scope"] = "industrial_effluent"

    variant = c9_variant(ans["setting"], final_phase)

    if variant == "single_band":
        special["c9_variant"] = "single_band"
        special["c9_band"] = ans.get("c9_voltage_band")

    elif final_phase == "Single":
        special["c9_variant"] = "farm_single_range"
        special["c9_min_v"] = ans.get("c9_min_v")
        special["c9_max_v"] = ans.get("c9_max_v")

    else:
        special["c9_variant"] = "three_phase_range"
        special["c9_min_v"] = ans.get("c9_min_v")
        special["c9_max_v"] = ans.get("c9_max_v")

    return {
        "allowed_pump_types": allowed_types,
        "required_min_head": required_min_head,
        "typical_head": typical_head,
        "required_min_flow": required_min_flow,
        "typical_flow": typical_flow,
        "daily_volume": rep_daily,
        "run_hours": run_hours,
        "allowed_phase": allowed_phase,
        "hp_cap": hp_cap,
        "final_phase": final_phase,
        "special": special,
    }
