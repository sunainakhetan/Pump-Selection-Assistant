"""
rules.py — Invalidity rules from the Pump Use-Case Framework doc.

Each rule is encoded as a predicate over a partial answers dict. The rule
returns one of:
    None                — does not apply / not triggered
    ("hard", reason)    — combination is invalid
    ("soft", reason)    — combination is allowed but a warning is shown

`evaluate(ans)` runs every rule and returns a list of (rule_id, severity, reason).
`is_disabled(field, candidate_value, ans)` is used by the UI to grey out an
option: it tries setting `ans[field] = candidate_value` and reports whether
any HARD rule fires solely because of the candidate.

Rule numbers match the framework doc exactly (1–74).
"""

# Lift-floor ordering used by several rules (low → high)
LIFT_ORDER = [
    "ground", "floor_1", "floor_2", "floor_3", "floor_4",
    "floors_5_10", "floors_11_15", "floors_16_25",
    "floors_26_40", "floors_41_60", "floors_above_60",
]


def _lift_idx(v):
    return LIFT_ORDER.index(v) if v in LIFT_ORDER else -1


def _lift_at_least(ans, threshold):
    """Returns True if ans['lift'] >= threshold in the lift ordering."""
    if not ans.get("lift"):
        return False
    return _lift_idx(ans["lift"]) >= _lift_idx(threshold)


# Each rule is a function (ans) -> None | ("hard"|"soft", reason)
# ---------------------------------------------------------------------------

# A. Job × Source -----------------------------------------------------------

def r1(a):
    if a.get("job") == "lift_and_store" and a.get("source") == "overhead_tank":
        return ("hard", "Overhead tank is already at height — nothing to lift.")

def r2(a):
    if a.get("job") == "lift_and_pressurise_directly" and a.get("source") == "overhead_tank":
        return ("hard", "Overhead tank already has gravity pressure — this is a boost case.")

def r3(a):
    if a.get("job") == "lift_and_store" and a.get("source") == "sewage_pit":
        return ("hard", "Sewage is not stored for reuse. Use 'Pump out sewage'.")

def r4(a):
    if a.get("job") == "lift_and_pressurise_directly" and a.get("source") == "sewage_pit":
        return ("hard", "Sewage is not pressurised into building lines.")

def r5(a):
    if a.get("job") == "boost_pressure" and a.get("source") == "sewage_pit":
        return ("hard", "Sewage pits are not a pressure source.")

def r6(a):
    if a.get("job") == "boost_pressure" and a.get("source") == "borewell":
        return ("hard", "A borewell needs lifting first — use 'Lift and pressurise directly'.")

def r7(a):
    if a.get("job") == "boost_pressure" and a.get("source") == "open_well":
        return ("hard", "Open wells are lifting sources, not pressurised supplies.")

def r8(a):
    if a.get("job") == "boost_pressure" and a.get("source") == "open_ground":
        return ("hard", "Surface irrigation sources are lifting sources, not pressurised.")

def r9(a):
    if a.get("job") == "drain_water" and a.get("source") in {"borewell", "overhead_tank", "municipal"}:
        return ("hard", "Drainage does not apply to borewells, overhead tanks, or supply mains.")

def r10(a):
    if a.get("job") == "drain_water" and a.get("source") == "open_ground":
        return ("hard", "Canals and rivers are not contained spaces needing drainage.")

def r11(a):
    if a.get("job") == "pump_sewage" and a.get("source") and a.get("source") != "sewage_pit":
        return ("hard", "Sewage pumping only applies to a sewage/drainage pit.")

def r12(a):
    if a.get("job") == "drain_water" and a.get("source") and \
       a.get("source") not in {"sewage_pit", "underground_sump"}:
        return ("hard", "Drainage operates on a contained collection point (pit or sump).")


# B. Job × Destination (C0) -------------------------------------------------

def r13(a):
    if a.get("job") == "lift_and_store" and a.get("c0_destination") == "direct_pipes":
        return ("hard", "Lift and store requires a storage destination.")

def r14(a):
    if a.get("job") == "lift_and_store" and a.get("c0_destination") == "irrigation":
        return ("hard", "Irrigation lines and fields are usage points, not storage.")

def r15(a):
    if a.get("job") == "lift_and_store" and a.get("c0_destination") == "industrial_process":
        return ("hard", "Industrial process consumes water — it is not storage.")

def r16(a):
    if a.get("job") == "lift_and_pressurise_directly" and a.get("c0_destination") == "overhead_tank":
        return ("hard", "Filling an overhead tank is storage, not direct pressurisation.")

def r17(a):
    if a.get("job") == "lift_and_pressurise_directly" and a.get("c0_destination") == "ground_sump":
        return ("hard", "Filling a sump is storage, not direct pressurisation.")

def r18(a):
    if a.get("job") == "lift_and_pressurise_directly" and a.get("c0_destination") == "tanker":
        return ("hard", "Loading a tanker is a transfer/storage operation.")


# C. Job × Lift -------------------------------------------------------------

def r19(a):
    if a.get("job") == "lift_and_store" and a.get("lift") == "ground":
        return ("hard", "A lift job requires water to be raised. Same-level is no lift.")

def r20(a):
    if a.get("job") == "lift_and_pressurise_directly" and a.get("lift") == "ground":
        return ("hard", "A lift job requires elevation change.")

def r21(a):
    if a.get("job") == "pump_sewage" and _lift_at_least(a, "floors_16_25"):
        return ("hard", "Sewage is not lifted 16+ floors in this framework's scope.")

def r22(a):
    if a.get("job") == "drain_water" and _lift_at_least(a, "floors_16_25"):
        return ("hard", "Drained water is not lifted 16+ floors in normal scope.")


# D. Job × Water Quality (C6) ----------------------------------------------

def r23(a):
    if a.get("job") == "pump_sewage" and a.get("c6_quality") == "clean_water":
        return ("hard", "Clean water contradicts sewage pumping. Use 'Drain or remove water'.")

def r24(a):
    if a.get("job") == "drain_water" and a.get("c6_quality") == "heavy_sewage":
        return ("hard", "Heavy sewage needs a sewage pump. Use 'Pump out sewage'.")


# E. Source × Destination ---------------------------------------------------

def r25(a):
    if a.get("source") == "overhead_tank" and a.get("c0_destination") == "overhead_tank":
        return ("hard", "Source and destination cannot both be the overhead tank.")

def r26(a):
    if a.get("source") == "underground_sump" and a.get("c0_destination") == "ground_sump":
        return ("hard", "Pumping sump-to-sump at the same level is not a normal use-case.")

def r27(a):
    if a.get("source") == "open_ground" and a.get("c0_destination") == "direct_pipes":
        return ("hard", "Surface water is not fed directly into building plumbing.")

def r28(a):
    if a.get("source") == "municipal" and a.get("c0_destination") == "industrial_process" \
       and a.get("setting") == "home":
        return ("hard", "Industrial process destination is implausible in a home.")


# F. Source × Lift ----------------------------------------------------------

def r29(a):
    if a.get("source") == "borewell" and a.get("lift") == "ground":
        return ("hard", "Borewell water must be lifted at least to the surface.")

def r30(a):
    if a.get("source") == "open_well" and a.get("lift") == "ground" \
       and a.get("job") in {"lift_and_store", "lift_and_pressurise_directly"}:
        return ("hard", "A lifting job from an open well needs elevation change.")

def r31(a):
    if a.get("source") == "open_well" and _lift_at_least(a, "floors_16_25"):
        return ("hard", "Open wells are shallow sources — high-rise use is out of scope.")

def r32(a):
    if a.get("source") == "underground_sump" and a.get("lift") == "ground" \
       and a.get("job") == "lift_and_store":
        return ("hard", "Lift and store from a sump implies lifting to higher storage.")


# G. Source × Setting / Demand ---------------------------------------------

def r33(a):
    if a.get("source") == "open_ground" and a.get("setting") == "home":
        return ("hard", "Canals/rivers are agricultural sources, not residential supply.")

def r34(a):
    if a.get("source") == "open_ground" and a.get("setting") == "shop_small_comm":
        return ("hard", "Canals/rivers are not used for small commercial supply.")

def r35(a):
    if a.get("source") == "open_ground" and a.get("setting") == "large_commercial":
        return ("hard", "Hotels/hospitals do not draw directly from canals or rivers.")

def r36(a):
    if a.get("source") == "municipal" and a.get("setting") == "farm":
        return ("hard", "Farms use borewells/ponds/canals — not municipal supply.")

def r37(a):
    if a.get("source") == "municipal" and a.get("demand") in {"very_large", "bulk"}:
        return ("hard", "Municipal supply does not deliver Very Large / Bulk volumes.")


# H. Destination × Setting / Lift / Demand ---------------------------------

def r38(a):
    if a.get("c0_destination") == "irrigation" and a.get("setting") and a.get("setting") != "farm":
        return ("hard", "Irrigation destinations are agricultural by definition.")

def r39(a):
    if a.get("c0_destination") == "industrial_process" \
       and a.get("setting") in {"home", "shop_small_comm"}:
        return ("hard", "Industrial process destinations are not residential or small-commercial.")

def r40(a):
    if a.get("c0_destination") == "tanker" and a.get("setting") == "home":
        return ("hard", "Loading water onto a tanker is not a residential use-case.")

def r41(a):
    if a.get("c0_destination") == "overhead_tank" and a.get("lift") == "ground":
        return ("hard", "Filling an overhead tank requires lifting; same-level contradicts this.")

def r42(a):
    if a.get("c0_destination") == "ground_sump" and _lift_at_least(a, "floor_3"):
        return ("hard", "Ground-level storage cannot be 3+ floors up.")

def r43(a):
    if a.get("c0_destination") == "tanker" and _lift_at_least(a, "floors_5_10"):
        return ("hard", "Tankers load at ground level; no reason to lift 5+ floors first.")


# I. Setting × Demand -------------------------------------------------------

def r44(a):
    if a.get("setting") == "home" and a.get("demand") in {"very_large", "bulk"}:
        return ("hard", "A single home does not consume 50,000+ litres/day.")

def r45(a):
    if a.get("setting") == "shop_small_comm" and a.get("demand") in {"very_large", "bulk"}:
        return ("hard", "Small commercial does not consume Very Large / Bulk volumes.")

def r46(a):
    if a.get("setting") == "farm" and a.get("demand") == "very_small":
        return ("hard", "Even the smallest farm plot exceeds 1,000 litres/day.")

def r47(a):
    if a.get("setting") == "large_commercial" and a.get("demand") in {"very_small", "small"}:
        return ("hard", "Hotels/hospitals/schools do not run on under 3,000 litres/day.")

def r48(a):
    if a.get("setting") == "light_industry" and a.get("demand") == "very_small":
        return ("hard", "Industry/warehouse/construction exceeds 1,000 litres/day in normal use.")


# J. Setting × Lift ---------------------------------------------------------

def r49(a):
    if a.get("setting") == "home" and _lift_at_least(a, "floors_5_10"):
        return ("hard", "Independent homes rarely exceed 4 floors. 5+ floors = large commercial.")

def r50(a):
    if a.get("setting") == "farm" and _lift_at_least(a, "floors_5_10"):
        return ("hard", "Farms do not have 5+ floor structures.")

def r51(a):
    if a.get("setting") == "shop_small_comm" and _lift_at_least(a, "floors_16_25"):
        return ("hard", "Small commercial premises are 1–6 floors typically.")

def r52(a):
    if a.get("setting") == "light_industry" and _lift_at_least(a, "floors_16_25"):
        return ("hard", "Light industry/warehouse/construction does not span 16+ floors.")


# K. Borewell internal consistency (C1 × C2 × Demand × Setting) ------------

def r53(a):
    deep = {"300_450ft", "450_600ft", "600_800ft", "800_1000ft", "above_1000ft"}
    if a.get("c1_casing") == "casing_4in" and a.get("c2_depth") in deep:
        return ("hard", "4-inch casing is for shallow borewells (~up to 300 ft).")

def r54(a):
    if a.get("c1_casing") == "casing_4in" and a.get("demand") in {"very_large", "bulk"}:
        return ("hard", "A 4-inch borewell pump cannot deliver Very Large / Bulk volumes.")

def r55(a):
    if a.get("c1_casing") == "casing_12in_plus" and a.get("setting") == "home":
        return ("hard", "12-inch casings are industrial/municipal — not domestic.")

def r56(a):
    if a.get("c1_casing") == "casing_10in" and a.get("setting") == "home":
        return ("hard", "10-inch casings are large agri/industrial — not residential.")

def r57(a):
    if a.get("c2_depth") == "above_1000ft" and a.get("setting") == "home" \
       and a.get("demand") in {"very_small", "small"}:
        return ("hard", "Drilling above 1,000 ft for tiny domestic demand is implausible.")


# L. Phase (C7) and Duty (C8) consistency ----------------------------------

def r58(a):
    if a.get("c7_phase") == "Single" \
       and a.get("setting") in {"farm", "light_industry", "large_commercial"} \
       and a.get("demand") in {"large", "very_large", "bulk"}:
        return ("hard", "Single-phase cannot support Large+ demand in these settings.")

def r59(a):
    # SOFT warning — Rule #59
    small_lifts = {"ground", "floor_1", "floor_2", "floor_3", "floor_4"}
    if a.get("c7_phase") == "Three" and a.get("setting") == "home" \
       and a.get("demand") in {"very_small", "small"} \
       and a.get("lift") in small_lifts:
        return ("soft", "Three-phase is unusual for a small home — please confirm supply.")

def r60(a):
    # C8 present but trigger not met
    triggered_settings = {"farm", "light_industry", "large_commercial"}
    triggered_demands = {"large", "very_large", "bulk"}
    if a.get("c8_duty") and a.get("setting") and a.get("demand"):
        if a["setting"] not in triggered_settings and a["demand"] not in triggered_demands:
            return ("hard", "Duty cycle should only be asked for industrial/large-demand cases.")

def r61(a):
    # C8 required but missing — only check if the user has reached the duty step
    triggered_settings = {"farm", "light_industry", "large_commercial"}
    triggered_demands = {"large", "very_large", "bulk"}
    if a.get("_completed") and not a.get("c8_duty") and a.get("setting") and a.get("demand"):
        if a["setting"] in triggered_settings or a["demand"] in triggered_demands:
            return ("hard", "Duty cycle is required for this setting/demand combination.")

def r62(a):
    if a.get("setting") == "home" and a.get("c8_duty") == "continuous":
        return ("hard", "12+ hour continuous pump duty is not a normal home use-case.")

def r63(a):
    if a.get("setting") == "shop_small_comm" and a.get("c8_duty") == "continuous":
        return ("hard", "Continuous duty indicates larger commercial/institutional use.")

def r64(a):
    if a.get("demand") == "very_small" and a.get("c8_duty") == "continuous":
        return ("hard", "Very small daily volume contradicts continuous 12+ hour duty.")

def r65(a):
    if a.get("demand") == "small" and a.get("c8_duty") == "continuous":
        return ("hard", "Small daily volume is inconsistent with continuous duty.")

def r66(a):
    if a.get("demand") in {"very_large", "bulk"} and a.get("c8_duty") == "moderate" \
       and a.get("setting") not in {"large_commercial", "light_industry", "farm"}:
        return ("hard", "Very large/bulk demand on moderate duty is implausible outside large-scale settings.")


# M. Pressure cluster (C4 × C5 × Demand × Setting) -------------------------

def r67(a):
    if a.get("c4_outlets") == "1_4" and a.get("c5_usage") in {"heavy", "constant_peak"}:
        return ("hard", "1–4 outlets cannot produce Heavy / Constant-peak usage.")

def r68(a):
    if a.get("c4_outlets") == "above_150" and a.get("c5_usage") == "light":
        return ("hard", "150+ outlets will always have multiple in use simultaneously.")

def r69(a):
    if a.get("c4_outlets") in {"36_75", "76_150", "above_150"} and a.get("setting") == "home":
        return ("hard", "A home does not have 36+ outlets.")

def r70(a):
    big = {"21_35", "36_75", "76_150", "above_150"}
    if a.get("c4_outlets") in big and a.get("demand") in {"very_small", "small"}:
        return ("hard", "21+ outlets cannot be served on Very Small / Small daily demand.")

def r71(a):
    if a.get("c4_outlets") == "1_4" and a.get("demand") in {"very_large", "bulk"}:
        return ("hard", "1–4 outlets cannot consume Very Large / Bulk daily volumes.")

def r72(a):
    if a.get("c4_outlets") in {"76_150", "above_150"} and a.get("setting") == "shop_small_comm":
        return ("hard", "76+ outlets is large commercial / institutional scale.")


# N. C9 voltage -------------------------------------------------------------
# Rules 73 and 74 are about trigger correctness (matcher-side). They are
# enforced by the UI's conditional logic and the matcher's data-quality
# handling; no extra runtime check is needed beyond not showing C9 when the
# final phase is Three.


ALL_RULES = [
    ("R1", r1), ("R2", r2), ("R3", r3), ("R4", r4), ("R5", r5),
    ("R6", r6), ("R7", r7), ("R8", r8), ("R9", r9), ("R10", r10),
    ("R11", r11), ("R12", r12), ("R13", r13), ("R14", r14), ("R15", r15),
    ("R16", r16), ("R17", r17), ("R18", r18), ("R19", r19), ("R20", r20),
    ("R21", r21), ("R22", r22), ("R23", r23), ("R24", r24), ("R25", r25),
    ("R26", r26), ("R27", r27), ("R28", r28), ("R29", r29), ("R30", r30),
    ("R31", r31), ("R32", r32), ("R33", r33), ("R34", r34), ("R35", r35),
    ("R36", r36), ("R37", r37), ("R38", r38), ("R39", r39), ("R40", r40),
    ("R41", r41), ("R42", r42), ("R43", r43), ("R44", r44), ("R45", r45),
    ("R46", r46), ("R47", r47), ("R48", r48), ("R49", r49), ("R50", r50),
    ("R51", r51), ("R52", r52), ("R53", r53), ("R54", r54), ("R55", r55),
    ("R56", r56), ("R57", r57), ("R58", r58), ("R59", r59), ("R60", r60),
    ("R61", r61), ("R62", r62), ("R63", r63), ("R64", r64), ("R65", r65),
    ("R66", r66), ("R67", r67), ("R68", r68), ("R69", r69), ("R70", r70),
    ("R71", r71), ("R72", r72),
]


def evaluate(ans: dict):
    """Return list of (rule_id, severity, reason) for every rule that fires."""
    out = []
    for rid, fn in ALL_RULES:
        try:
            res = fn(ans)
        except Exception:
            res = None
        if res:
            out.append((rid, res[0], res[1]))
    return out


def is_disabled(field: str, candidate, ans: dict):
    """
    Would selecting `field = candidate` introduce a HARD violation that did
    not exist before? Used to grey-out options in the UI.

    Returns (disabled: bool, reason: str|None).
    """
    # Hard violations already present before the candidate
    before_hard = {(rid, reason) for (rid, sev, reason) in evaluate(ans) if sev == "hard"}
    trial = dict(ans)
    trial[field] = candidate
    after = evaluate(trial)
    after_hard = {(rid, reason) for (rid, sev, reason) in after if sev == "hard"}
    new_hard = after_hard - before_hard
    if new_hard:
        rid, reason = next(iter(new_hard))
        return True, f"{rid}: {reason}"
    return False, None
