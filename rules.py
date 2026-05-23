"""
rules.py — v0.6 customer-path invalidity rules.

Rules return None or ("hard"|"soft", reason). They intentionally operate on a
partial answer dict so the UI can disable impossible options as soon as they
become impossible.
"""

from vector import daily_volume, c8_triggered, c9_variant

LIFT_ORDER = [
    "ground", "floor_1", "floor_2", "floor_3", "floor_4",
    "floors_5_10", "floors_11_15", "floors_16_25",
    "floors_26_40", "floors_41_60", "floors_above_60",
]

PRESSURE_JOBS = {"boost_pressure", "lift_and_pressurise_directly"}


def _lift_idx(v):
    return LIFT_ORDER.index(v) if v in LIFT_ORDER else -1


def _lift_at_least(a, threshold):
    return a.get("lift") in LIFT_ORDER and _lift_idx(a["lift"]) >= _lift_idx(threshold)


def _dv(a):
    try:
        return daily_volume(a)
    except Exception:
        return None


def _has(a, *keys):
    return all(a.get(k) is not None for k in keys)


# A. Job × Source -----------------------------------------------------------
def r1(a):
    if a.get("job") == "lift_and_store" and a.get("source") == "overhead_tank":
        return ("hard", "Overhead tank is already at height — nothing to lift.")


def r2(a):
    if a.get("job") == "lift_and_pressurise_directly" and a.get("source") == "overhead_tank":
        return ("hard", "Overhead tank already has gravity pressure; this is a boost case.")


def r3(a):
    if a.get("job") == "lift_and_store" and a.get("source") == "sewage_pit":
        return ("hard", "Sewage/drainage water is not stored for reuse.")


def r4(a):
    if a.get("job") == "lift_and_pressurise_directly" and a.get("source") == "sewage_pit":
        return ("hard", "Sewage is not pressurised into building lines.")


def r5(a):
    if a.get("job") == "boost_pressure" and a.get("source") == "borewell":
        return ("hard", "Borewell water must be lifted first; boost applies only at the pump inlet.")


def r6(a):
    if a.get("job") == "boost_pressure" and a.get("source") == "open_well":
        return ("hard", "Open wells are lifting sources, not pressure sources.")


def r7(a):
    if a.get("job") == "boost_pressure" and a.get("source") == "sewage_pit":
        return ("hard", "Sewage is removed, not boosted to fixtures.")


def r8(a):
    if a.get("job") == "boost_pressure" and a.get("source") == "open_ground":
        return ("hard", "Surface irrigation sources are not pressurised supplies.")


def r9(a):
    if a.get("job") == "drain_water" and a.get("source") in {
        "borewell", "open_well", "overhead_tank", "municipal", "open_ground"
    }:
        return ("hard", "Drainage applies to collection points, not supply sources.")


def r10(a):
    if a.get("job") == "pump_sewage" and a.get("source") in {
        "borewell", "open_well", "overhead_tank", "municipal", "open_ground"
    }:
        return ("hard", "Sewage is pumped from sewage/drainage pits, not supply sources.")


def r11(a):
    if a.get("job") == "pump_sewage" and a.get("source") == "underground_sump":
        return ("hard", "Underground sumps hold clean stored water, not sewage.")


def r12(a):
    if a.get("job") == "drain_water" and a.get("source") == "underground_sump":
        return ("hard", "Storage sumps are not normally drainage collection points.")


# B. Job × Destination ------------------------------------------------------
def r13(a):
    if a.get("job") == "lift_and_store" and a.get("c0_destination") == "direct_pipes":
        return ("hard", "Lift and store requires storage; direct pipes are not storage.")


def r14(a):
    if a.get("job") == "lift_and_store" and a.get("c0_destination") == "irrigation":
        return ("hard", "Irrigation lines are usage points, not storage.")


def r15(a):
    if a.get("job") == "lift_and_store" and a.get("c0_destination") == "industrial_process":
        return ("hard", "Industrial process consumes water; it is not storage.")


def r16(a):
    if a.get("job") == "lift_and_pressurise_directly" and a.get("c0_destination") == "overhead_tank":
        return ("hard", "Filling an overhead tank is storage, not direct pressurisation.")


def r17(a):
    if a.get("job") == "lift_and_pressurise_directly" and a.get("c0_destination") == "ground_sump":
        return ("hard", "Filling a sump is storage, not direct pressurisation.")


def r18(a):
    if a.get("job") == "lift_and_pressurise_directly" and a.get("c0_destination") == "tanker":
        return ("hard", "Loading a tanker is a transfer/storage operation.")


# C/D/E/F/G/H/I/J/K ---------------------------------------------------------
def r19(a):
    if a.get("job") == "lift_and_store" and a.get("lift") == "ground":
        return ("hard", "A lift job requires elevation change.")


def r20(a):
    if a.get("job") == "lift_and_pressurise_directly" and a.get("lift") == "ground":
        return ("hard", "A lift job requires elevation change.")


def r21(a):
    if a.get("job") == "pump_sewage" and _lift_at_least(a, "floors_16_25"):
        return ("hard", "Sewage lifting 16+ floors is outside this framework's scope.")


def r22(a):
    if a.get("job") == "drain_water" and _lift_at_least(a, "floors_16_25"):
        return ("hard", "Drainage lifting 16+ floors is outside normal scope.")


def r23(a):
    if a.get("job") == "pump_sewage" and a.get("c6_quality") == "clean_water":
        return ("hard", "Clean water contradicts sewage pumping.")


def r24(a):
    if a.get("job") == "drain_water" and a.get("c6_quality") == "heavy_sewage":
        return ("hard", "Heavy sewage requires a sewage-pumping path.")


def r25(a):
    if a.get("source") == "overhead_tank" and a.get("c0_destination") == "overhead_tank":
        return ("hard", "Source and destination cannot both be the overhead tank.")


def r26(a):
    if a.get("source") == "underground_sump" and a.get("c0_destination") == "ground_sump":
        return ("hard", "Sump-to-sump at the same level is not a normal use-case.")


def r27(a):
    if a.get("source") == "open_ground" and a.get("c0_destination") == "direct_pipes":
        return ("hard", "Surface water is not fed directly into building plumbing.")


def r28(a):
    if a.get("source") == "municipal" and a.get("c0_destination") == "industrial_process" and a.get("setting") == "home":
        return ("hard", "Industrial process destination is implausible in a home.")


def r29(a):
    if a.get("source") == "borewell" and a.get("lift") == "ground":
        return ("hard", "Borewell water must be lifted at least to the surface.")


def r30(a):
    if a.get("source") == "open_well" and a.get("lift") == "ground" and a.get("job") in {
        "lift_and_store", "lift_and_pressurise_directly"
    }:
        return ("hard", "A lifting job from an open well needs elevation change.")


def r31(a):
    if a.get("source") == "open_well" and _lift_at_least(a, "floors_16_25"):
        return ("hard", "Open wells/ponds are not used for high-rise pumping in this framework.")


def r32(a):
    if a.get("source") == "underground_sump" and a.get("lift") == "ground" and a.get("job") == "lift_and_store":
        return ("hard", "Lift and store from a sump implies lifting to higher storage.")


def r33(a):
    if a.get("source") == "open_ground" and a.get("setting") == "home":
        return ("hard", "Canals/rivers are agricultural sources, not residential supply.")


def r34(a):
    if a.get("source") == "open_ground" and a.get("setting") == "shop_small_comm":
        return ("hard", "Canals/rivers are not small-commercial supply sources.")


def r35(a):
    if a.get("source") == "open_ground" and a.get("setting") == "large_commercial":
        return ("hard", "Large commercial/institutional buildings do not draw directly from canals or rivers.")


def r36(a):
    if a.get("source") == "municipal" and a.get("setting") == "farm":
        return ("hard", "Farms normally use borewell/open-ground sources, not municipal supply.")


def r37(a):
    if a.get("source") == "municipal" and (_dv(a) or 0) >= 50000:
        return ("hard", "Municipal direct supply does not deliver 50,000+ L/day.")


def r38(a):
    if a.get("c0_destination") == "irrigation" and a.get("setting") and a.get("setting") != "farm":
        return ("hard", "Irrigation/livestock destinations are agricultural.")


def r39(a):
    if a.get("c0_destination") == "industrial_process" and a.get("setting") in {"home", "shop_small_comm"}:
        return ("hard", "Industrial process destinations are not residential or small-commercial.")


def r40(a):
    if a.get("c0_destination") == "tanker" and a.get("setting") == "home":
        return ("hard", "Tanker loading is not a residential use-case.")


def r41(a):
    if a.get("c0_destination") == "overhead_tank" and a.get("lift") == "ground":
        return ("hard", "Filling an overhead tank requires lift.")


def r42(a):
    if a.get("c0_destination") == "ground_sump" and _lift_at_least(a, "floor_3"):
        return ("hard", "Ground-level storage cannot be 3+ floors up.")


def r43(a):
    if a.get("c0_destination") == "tanker" and _lift_at_least(a, "floors_5_10"):
        return ("hard", "Tankers load at ground level.")


def r44(a):
    if a.get("setting") == "home" and (_dv(a) or 0) > 5000:
        return ("hard", "Home demand tops out at the large independent home / farmhouse band.")


def r45(a):
    if a.get("setting") == "shop_small_comm" and (_dv(a) or 0) > 10000:
        return ("hard", "Small-commercial demand tops out at 10,000 L/day.")


def r46(a):
    return None


def r47(a):
    if a.get("setting") == "large_commercial" and _has(a, "demand") and (_dv(a) or 0) < 2000:
        return ("hard", "Large commercial/institutional premises do not run below 2,000 L/day.")


def r48(a):
    if a.get("setting") == "light_industry" and _has(a, "demand") and (_dv(a) or 0) < 200:
        return ("hard", "Light industry starts at 200+ L/day.")


def r49(a):
    if a.get("setting") == "home" and _lift_at_least(a, "floors_5_10"):
        return ("hard", "Independent homes rarely exceed 4 floors; 5+ floors belongs to large commercial/institutional.")


def r50(a):
    if a.get("setting") == "farm" and _lift_at_least(a, "floors_5_10"):
        return ("hard", "Farms do not have 5+ floor structures.")


def r51(a):
    if a.get("setting") == "shop_small_comm" and _lift_at_least(a, "floors_16_25"):
        return ("hard", "Small commercial is normally not 16+ floors.")


def r52(a):
    if a.get("setting") == "light_industry" and _lift_at_least(a, "floors_16_25"):
        return ("hard", "Light industry/warehouse/construction does not normally span 16+ floors.")


def r53(a):
    if a.get("c1_casing") == "casing_4in" and a.get("c2_depth") in {
        "300_450ft", "450_600ft", "600_800ft", "800_1000ft", "above_1000ft"
    }:
        return ("hard", "4-inch casing is for shallow borewells up to about 300 ft.")


def r54(a):
    if a.get("c1_casing") == "casing_4in" and (_dv(a) or 0) >= 50000:
        return ("hard", "4-inch borewell casing cannot serve 50,000+ L/day.")


def r55(a):
    if a.get("c1_casing") == "casing_12in_plus" and a.get("setting") == "home":
        return ("hard", "12-inch casings are industrial/municipal, not domestic.")


def r56(a):
    if a.get("c1_casing") == "casing_10in" and a.get("setting") == "home":
        return ("hard", "10-inch casings are large agri/industrial, not residential.")


def r57(a):
    if a.get("c2_depth") == "above_1000ft" and a.get("setting") == "home" and (_dv(a) or 999999) <= 2000:
        return ("hard", "Extra-deep borewell for small domestic demand is implausible.")


# L. Phase / Duty -----------------------------------------------------------
def r58(a):
    if a.get("c7_phase") == "Single" and a.get("setting") in {"farm", "light_industry", "large_commercial"} and (_dv(a) or 0) >= 10000:
        return ("hard", "High-volume farm, industrial, or large-commercial duty requires three-phase.")


def r59(a):
    if a.get("c7_phase") == "Three" and a.get("setting") == "home" and (_dv(a) or 999999) <= 2000 and a.get("lift") in {
        "ground", "floor_1", "floor_2", "floor_3", "floor_4"
    }:
        return ("soft", "Three-phase on a small, low-lift home is unusual; confirm service before purchase.")


def r60(a):
    if a.get("c8_duty") and not c8_triggered(a):
        return ("hard", "Duty cycle is only asked for farm, large commercial, light industry, or volume ≥ 10,000 L/day.")


def r61(a):
    if _has(a, "setting", "demand") and c8_triggered(a) and not a.get("c8_duty"):
        return ("hard", "Duty cycle is required for this setting or volume.")


def r62(a):
    if a.get("setting") == "home" and a.get("c8_duty") == "continuous":
        return ("hard", "Continuous operation is not a normal Home use-case.")


def r63(a):
    if a.get("setting") == "shop_small_comm" and a.get("c8_duty") == "continuous":
        return ("hard", "Continuous duty indicates a larger commercial/institutional/industrial setting.")


def r64(a):
    if (_dv(a) or 999999) <= 1000 and a.get("c8_duty") == "continuous":
        return ("hard", "Very low volume contradicts continuous duty.")


def r65(a):
    if (_dv(a) or 999999) <= 3000 and a.get("c8_duty") == "continuous":
        return ("hard", "Low volume is inconsistent with continuous 12+ hour duty.")


def r66(a):
    if (_dv(a) or 0) >= 50000 and a.get("c8_duty") == "moderate" and a.get("setting") not in {
        "large_commercial", "light_industry", "farm"
    }:
        return ("hard", "High volume with moderate duty is inconsistent outside large-scale settings.")


# M/N/O. Pressure cluster, C9, C5a -----------------------------------------
def r67(a):
    if a.get("c4_outlets") == "1_4" and a.get("c5_usage") in {"heavy", "constant_peak"} and a.get("c5a_pressure") != "home_premium":
        return ("hard", "1–4 outlets cannot normally have Heavy/Constant-peak use unless premium fittings are selected.")


def r68(a):
    if a.get("c4_outlets") == "above_150" and a.get("c5_usage") == "light":
        return ("hard", "150+ outlets cannot have only light simultaneous use.")


def r69(a):
    if a.get("c4_outlets") in {"36_75", "76_150", "above_150"} and a.get("setting") == "home":
        return ("hard", "Individual homes do not have 36+ outlets.")


def r70(a):
    if a.get("c4_outlets") in {"21_35", "36_75", "76_150", "above_150"} and (_dv(a) or 999999) <= 3000:
        return ("hard", "21+ outlets contradict a daily volume at or below 3,000 L/day.")


def r71(a):
    if a.get("c4_outlets") == "1_4" and (_dv(a) or 0) >= 50000:
        return ("hard", "1–4 outlets cannot consume 50,000+ L/day.")


def r72(a):
    if a.get("c4_outlets") in {"76_150", "above_150"} and a.get("setting") == "shop_small_comm":
        return ("hard", "76+ outlets is large-commercial/institutional scale.")


def r73(a):
    if not _has(a, "setting"):
        return None
    phase = a.get("c7_phase")
    if not phase:
        return None
    variant = c9_variant(a["setting"], phase)
    has_band = a.get("c9_voltage_band") is not None
    has_range = a.get("c9_min_v") is not None or a.get("c9_max_v") is not None
    if variant == "single_band" and has_range:
        return ("hard", "C9 answer shape must be the single-phase two-band picker for this setting and phase.")
    if variant != "single_band" and has_band:
        return ("hard", "C9 answer shape must be Min/Max voltage for this setting and phase.")


def r74(a):
    if not _has(a, "setting"):
        return None
    phase = a.get("c7_phase")
    if not phase:
        return None
    variant = c9_variant(a["setting"], phase)
    if variant == "single_band":
        if not a.get("c9_voltage_band"):
            return ("hard", "C9 voltage band is required.")
    else:
        if a.get("c9_min_v") is None or a.get("c9_max_v") is None:
            return ("hard", "C9 Min V and Max V are required.")
        if a.get("c9_min_v") >= a.get("c9_max_v"):
            return ("hard", "C9 Min V must be below Max V.")


def r75(a):
    if a.get("c5a_pressure") and a.get("job") not in PRESSURE_JOBS:
        return ("hard", "C5a only triggers for pressure jobs.")


def r76(a):
    if a.get("job") in PRESSURE_JOBS and not a.get("c5a_pressure"):
        return ("hard", "C5a fixture/application pressure class is required for pressure jobs.")


def r77(a):
    if a.get("c5a_pressure") == "home_premium" and a.get("setting") == "light_industry":
        return ("hard", "Premium bathroom fittings are not an industrial application.")


def r78(a):
    if a.get("c5a_pressure") == "home_premium" and a.get("setting") == "farm":
        return ("hard", "Premium bathroom fittings are not a farm C5a option.")


def r79(a):
    if a.get("c5a_pressure") in {"industry_routine_wash", "industry_heavy_jetting"} and a.get("setting") == "home":
        return ("hard", "Industrial wash/jetting is not residential.")


def r80(a):
    if a.get("c5a_pressure") == "farm_rain_gun" and a.get("setting") == "farm" and a.get("demand") in {"vol_800", "vol_2000"}:
        return ("soft", "Rain guns are unusual for a homestead/backyard-livestock farm band.")


def r81(a):
    if a.get("c5a_pressure") == "industry_heavy_jetting" and a.get("setting") == "light_industry" and a.get("demand") in {"vol_800", "vol_2000"}:
        return ("soft", "Heavy industrial jetting is unusual at the smallest light-industry bands.")


RULES = [globals()[f"r{i}"] for i in range(1, 82)]


def evaluate(ans):
    out = []
    for i, rule in enumerate(RULES, 1):
        try:
            res = rule(ans)
        except Exception:
            res = None
        if res:
            sev, reason = res
            out.append((i, sev, reason))
    return out


def is_disabled(field, candidate_value, ans):
    test = dict(ans)
    test[field] = candidate_value
    existing = {i for i, sev, _ in evaluate(ans) if sev == "hard"}
    for i, sev, reason in evaluate(test):
        if sev == "hard" and i not in existing:
            return True, reason
    return False, None
