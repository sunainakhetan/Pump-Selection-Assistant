"""
vector.py — build the requirement vector from validated customer answers.

Source of truth for all numbers/mappings:
  - Pump_UseCase_Framework___mapping_tables_FINAL.docx
  - FILTERING_AND_SCORING_MECHANISM_FINAL.docx

The requirement vector is the compact summary used by the SKU matcher.
Fields (per the filtering doc, section 2):
  - allowed_pump_types     : list[str]   (Job ∩ Source, refined by C3/C6)
  - required_min_head      : float (m)   (Lift floor + C2/C3 depth)
  - typical_head           : float (m)   (Lift typical + C2/C3 depth)
  - required_min_flow      : float (LPH) (max of demand min, demand/run, outlet×C5)
  - typical_flow           : float (LPH) (max of demand typical, required×1.15)
  - allowed_phase          : set[str]    (subset of {'Single','Three','Both'})
  - hp_cap                 : float|None  (preferred soft cap; hard cap is 2× this)
  - special                : dict        (borewell V-codes, required suction lift,
                                          cutter requirement, c9 voltage band, etc.)
"""

# ---------------------------------------------------------------------------
# Core lookup tables (transcribed verbatim from the framework + filtering doc)
# ---------------------------------------------------------------------------

# Job → eligible pump types (mapping doc, Factor 1)
JOB_TYPES = {
    "lift_and_store": ["Self-Priming Pump", "Openwell Pump", "Borewell Pump"],
    "lift_and_pressurise_directly": [
        "Self-Priming Pump", "Openwell Pump", "Borewell Pump",
        "Pressure Booster Pump", "Hydropneumatic Pump",
    ],
    "boost_pressure": ["Pressure Booster Pump", "Hydropneumatic Pump"],
    "drain_water": ["Self-Priming Pump", "Sewage Pump"],
    "pump_sewage": ["Sewage Pump"],
}

# Source → eligible pump types and required suction lift for self-priming
# (mapping doc, Factor 2)
SOURCE_TYPES = {
    "borewell":        {"types": ["Borewell Pump"],                                              "suction_required": None},
    "open_well":       {"types": ["Openwell Pump", "Self-Priming Pump", "Borewell Pump"],        "suction_required": 6},
    "underground_sump":{"types": ["Self-Priming Pump", "Openwell Pump", "Hydropneumatic Pump"],  "suction_required": 6},
    "overhead_tank":   {"types": ["Pressure Booster Pump", "Hydropneumatic Pump"],               "suction_required": 0},
    "municipal":       {"types": ["Self-Priming Pump", "Pressure Booster Pump", "Hydropneumatic Pump"], "suction_required": 3},
    "sewage_pit":      {"types": ["Self-Priming Pump", "Sewage Pump"],                           "suction_required": 3},
    "open_ground":     {"types": ["Openwell Pump", "Self-Priming Pump"],                         "suction_required": 6},
}

# Lift → (min head m, typical head m)
# Per filtering doc section 3.
LIFT_HEAD = {
    "ground":        (0,   5),
    "floor_1":       (6,   12),
    "floor_2":       (9,   15),
    "floor_3":       (12,  18),
    "floor_4":       (15,  22),
    "floors_5_10":   (30,  40),
    "floors_11_15":  (45,  55),
    "floors_16_25":  (75,  85),
    "floors_26_40":  (120, 135),
    "floors_41_60":  (180, 200),
    "floors_above_60": (180, 220),   # "180m+ / 220m+" — use the floor of each
}

# Demand → (default run-hours, min flow LPH, typical flow LPH)
# Filtering doc section 4.
DEMAND_FLOW = {
    "very_small": (2,  500,    800),
    "small":      (3,  1000,   1500),
    "medium":     (4,  2500,   3500),
    "large":      (6,  8000,   12000),
    "very_large": (8,  25000,  40000),
    "bulk":       (10, 50000,  80000),
}

# Setting → (default phase, preferred HP cap)
# Mapping doc Factor 5. None means no HP cap (Farm, Large commercial, Light industry).
SETTING_DEFAULTS = {
    "home":              ("Single", 3),
    "farm":              ("Three",  None),
    "shop_small_comm":   ("Single", 3),
    "large_commercial":  ("Three",  None),
    "light_industry":    ("Three",  None),
}

# Per-outlet flow assumption (LPH) by setting — mapping doc C4
PER_OUTLET_FLOW = {
    "home":              600,
    "shop_small_comm":   600,
    "farm":              900,
    "large_commercial":  900,
    "light_industry":    900,
}

# C5 simultaneous usage multiplier
USAGE_MULT = {"light": 0.3, "moderate": 0.5, "heavy": 0.7, "constant_peak": 1.0}

# C8 → representative run-hours used in flow calc (mapping doc)
C8_HOURS = {"moderate": 4, "heavy": 9, "continuous": 14}

# C1 borewell casing → eligible V-codes (mapping doc)
C1_VCODES = {
    "casing_4in":  ["V3", "V3.5"],
    "casing_6in":  ["V3", "V3.5", "V4", "V5"],
    "casing_8in":  ["V3", "V3.5", "V4", "V5", "V6", "V7"],
    "casing_10in": ["V3", "V3.5", "V4", "V5", "V6", "V7", "V8", "V9"],
    "casing_12in_plus": ["V3", "V3.5", "V4", "V5", "V6", "V7", "V8", "V9", "V10"],
}

# C2 borewell static rest level → metres added to head (mapping doc)
C2_HEAD_ADD = {
    "under_50ft":   15,
    "50_100ft":     30,
    "100_200ft":    60,
    "200_300ft":    90,
    "300_450ft":    135,
    "450_600ft":    180,
    "600_800ft":    245,
    "800_1000ft":   305,
    "above_1000ft": 350,
}

# C3 open-well depth → (head add metres, refined eligible types from {SP,OW,BW})
C3_HEAD_ADD = {
    "shallow_under_30ft": (9,  ["Self-Priming Pump", "Openwell Pump"]),
    "medium_30_60ft":     (18, ["Openwell Pump", "Self-Priming Pump"]),
    "deep_above_60ft":    (25, ["Openwell Pump", "Borewell Pump"]),
}

# C4 outlet bands — just used for UI; flow calc uses outlet count × per-outlet × C5
# C6 water quality → refined types + cutter requirement (mapping doc)
C6_RULES = {
    "clean_water":     {"types": ["Self-Priming Pump", "Sewage Pump"], "cutter": None,           "out_of_scope": False},
    "lightly_soiled":  {"types": ["Sewage Pump"],                       "cutter": "non-cutter",  "out_of_scope": False},
    "solids_waste":    {"types": ["Sewage Pump"],                       "cutter": "with cutter", "out_of_scope": False},
    "heavy_sewage":    {"types": ["Sewage Pump"],                       "cutter": "with cutter", "out_of_scope": False},
    "industrial_effluent": {"types": [],                                "cutter": None,           "out_of_scope": True},
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _intersect(a, b):
    """Order-preserving intersection of two type lists."""
    return [x for x in a if x in b]


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

def build_vector(ans: dict) -> dict:
    """
    Convert a dict of customer answers into the requirement vector.

    `ans` keys (only those triggered will be present):
      job, source, lift, demand, setting,
      c0_destination, c1_casing, c2_depth, c3_well_depth,
      c4_outlets_count (int), c5_usage, c6_quality,
      c7_phase, c8_duty, c9_voltage
    """

    # ---- 1. allowed pump types: Job ∩ Source, refined by C3 / C6 ---------
    job_types = JOB_TYPES[ans["job"]]
    src_types = SOURCE_TYPES[ans["source"]]["types"]
    allowed_types = _intersect(job_types, src_types)

    if ans.get("c3_well_depth"):
        _, refined = C3_HEAD_ADD[ans["c3_well_depth"]]
        allowed_types = _intersect(allowed_types, refined)

    if ans.get("c6_quality"):
        rule = C6_RULES[ans["c6_quality"]]
        if rule["out_of_scope"]:
            allowed_types = []
        else:
            allowed_types = _intersect(allowed_types, rule["types"])

    # ---- 2. head: Lift band + C2/C3 depth allowance ----------------------
    lift_min, lift_typ = LIFT_HEAD[ans["lift"]]
    head_add = 0
    if ans.get("c2_depth"):
        head_add += C2_HEAD_ADD[ans["c2_depth"]]
    if ans.get("c3_well_depth"):
        head_add += C3_HEAD_ADD[ans["c3_well_depth"]][0]
    required_min_head = lift_min + head_add
    typical_head = lift_typ + head_add

    # ---- 3. flow: max of (demand-min, demand/run-hours, outlet×C5) -------
    run_hours, demand_min_flow, demand_typ_flow = DEMAND_FLOW[ans["demand"]]
    if ans.get("c8_duty"):
        run_hours = C8_HOURS[ans["c8_duty"]]

    daily_litres_map = {
        "very_small": 1000, "small": 3000, "medium": 10000,
        "large": 50000, "very_large": 200000, "bulk": 400000,
    }
    daily_volume = daily_litres_map[ans["demand"]]
    demand_based_flow = daily_volume / run_hours

    outlet_based_flow = 0
    if ans.get("c4_outlets_count") and ans.get("c5_usage"):
        per_outlet = PER_OUTLET_FLOW[ans["setting"]]
        outlet_based_flow = ans["c4_outlets_count"] * per_outlet * USAGE_MULT[ans["c5_usage"]]

    required_min_flow = max(demand_min_flow, demand_based_flow, outlet_based_flow)
    typical_flow = max(demand_typ_flow, required_min_flow * 1.15)

    # ---- 4. phase --------------------------------------------------------
    default_phase, hp_cap = SETTING_DEFAULTS[ans["setting"]]
    final_phase = ans.get("c7_phase") or default_phase
    if final_phase == "Single":
        allowed_phase = {"Single", "Both"}
    else:
        allowed_phase = {"Three", "Both"}

    # ---- 5. special filters ---------------------------------------------
    special = {}

    if ans["source"] == "borewell" and ans.get("c1_casing"):
        special["borewell_vcodes"] = C1_VCODES[ans["c1_casing"]]

    suction_required = SOURCE_TYPES[ans["source"]]["suction_required"]
    if suction_required is not None:
        special["suction_lift_required"] = suction_required

    if ans.get("c6_quality"):
        cutter = C6_RULES[ans["c6_quality"]]["cutter"]
        if cutter is not None:
            special["cutter_required"] = cutter
        if C6_RULES[ans["c6_quality"]]["out_of_scope"]:
            special["out_of_scope"] = "industrial_effluent"

    if final_phase == "Single" and ans.get("c9_voltage"):
        special["c9_voltage"] = ans["c9_voltage"]

    return {
        "allowed_pump_types": allowed_types,
        "required_min_head": required_min_head,
        "typical_head": typical_head,
        "required_min_flow": required_min_flow,
        "typical_flow": typical_flow,
        "allowed_phase": allowed_phase,
        "hp_cap": hp_cap,
        "final_phase": final_phase,
        "special": special,
    }
