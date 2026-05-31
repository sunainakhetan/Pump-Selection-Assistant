"""
rules.py — Pump Use-Case Framework v1.2 invalidity and warning checks.

The UI uses the matrix helpers in vector.py to disable impossible paths early;
this module provides transparent rule-style diagnostics for the current partial
or complete answer set.
"""

from __future__ import annotations

from vector import (
    C5A_ALLOWED_BY_SETTING,
    C6_RULES,
    FARM_OUTLET_ALLOWED,
    FARM_SINGLE_MAX_VALUES,
    FARM_SINGLE_MIN_VALUES,
    JOBS,
    LOW_C9_BAND,
    MATRIX,
    NORMAL_C9_BAND,
    SETTINGS,
    SOURCES,
    THREE_MAX_VALUES,
    THREE_MIN_VALUES,
    available_destinations,
    available_sources,
    c8_triggered,
    c9_variant,
    daily_volume,
    default_phase,
    final_phase,
    lift_triggered,
    matrix_key,
    needs_phase_confirm,
)


def _has(a: dict, *keys: str) -> bool:
    return all(a.get(k) is not None for k in keys)


def _soft_warnings(a: dict) -> list[tuple[int, str, str]]:
    out = []
    if (
        a.get("setting") == "home"
        and a.get("job") == "boost_pressure"
        and a.get("c5a_pressure") == "home_premium"
        and a.get("c4_outlets") in {"1_4", "5_12"}
    ):
        out.append((42, "soft", "Premium home fixtures on a small outlet band: applying the 3,000 / 3,500 LPH flow floor."))

    if (
        a.get("setting") == "farm"
        and a.get("job") == "boost_pressure"
        and a.get("c5a_pressure") == "farm_rain_gun"
        and daily_volume(a) is not None
        and daily_volume(a) < 10000
    ):
        out.append((43, "soft", "Rain guns / high-pressure sprinklers with demand below 10,000 L/day: review the irrigation duty."))

    if (
        a.get("setting") == "light_industry"
        and a.get("job") == "boost_pressure"
        and a.get("c5a_pressure") == "industry_heavy_jetting"
        and daily_volume(a) is not None
        and daily_volume(a) < 5000
    ):
        out.append((44, "soft", "Heavy wash-down / jetting with demand below 5,000 L/day: review the pressure class."))
    return out


def evaluate(a: dict) -> list[tuple[int, str, str]]:
    """Return (rule_id, severity, reason) tuples for the supplied answers."""

    a = dict(a)
    if a.get("job") == "drain_sewage":
        a["source"] = "sewage_pit"
        a["c0_destination"] = None

    issues: list[tuple[int, str, str]] = []

    # Vocabulary sanity.
    if a.get("setting") and a["setting"] not in SETTINGS:
        issues.append((1, "hard", "Unknown Setting answer."))
    if a.get("job") and a["job"] not in JOBS:
        issues.append((2, "hard", "Unknown Job answer."))
    if a.get("source") and a["source"] not in SOURCES:
        issues.append((3, "hard", "Unknown Source answer."))

    # Matrix gate and option filtering.
    if a.get("setting") and a.get("job") and a["job"] not in {j for _s, j, _src, _d in MATRIX if _s == a["setting"]}:
        issues.append((7, "hard", "This Setting × Job combination is not enabled."))

    if _has(a, "setting", "job") and a.get("source"):
        allowed = available_sources(a["setting"], a["job"])
        if a["source"] not in allowed:
            issues.append((7, "hard", "This Source is not enabled for the selected Setting × Job path."))

    if a.get("job") in {"lift_and_store", "boost_pressure"} and _has(a, "setting", "source") and a.get("c0_destination"):
        allowed_dest = available_destinations(a["setting"], a["job"], a["source"])
        if a["c0_destination"] not in allowed_dest:
            issues.append((7, "hard", "This Destination is not enabled for the selected Setting × Job × Source path."))

    key = matrix_key(a)
    if key is not None and key not in MATRIX:
        issues.append((7, "hard", "The complete Setting × Job × Source × Destination tuple is not in the enabled matrix."))

    # Destination / source visibility.
    if a.get("job") == "drain_sewage" and a.get("c0_destination") is not None:
        issues.append((9, "hard", "Drain sewage / water never asks Destination."))
    if a.get("job") != "drain_sewage" and a.get("source") == "sewage_pit":
        issues.append((36, "hard", "Sewage or drainage pit appears only for Drain sewage / water."))
    if a.get("source") == "municipal" and a.get("job") == "boost_pressure":
        issues.append((37, "hard", "Municipal / shared piped supply is not enabled for Boost pressure in v1.2."))

    # Lift trigger and visibility.
    if a.get("lift") is not None and not lift_triggered(a):
        issues.append((11, "hard", "Lift was answered even though this path does not need a lift value."))
    if lift_triggered(a) and a.get("lift") is None:
        issues.append((10, "hard", "Please select the number of floors the water needs to reach."))

    # Source-depth visibility.
    if a.get("source") == "borewell" and a.get("c2_depth_m") is None:
        issues.append((14, "hard", "Borewell source requires the C2 static rest level slider."))
    if a.get("source") != "borewell" and a.get("c2_depth_m") is not None:
        issues.append((19, "hard", "C2 belongs only to Borewell sources."))

    if a.get("source") == "open_well" and a.get("c3_depth_m") is None:
        issues.append((15, "hard", "Open well / pond source requires the C3 water-depth slider."))
    if a.get("source") != "open_well" and a.get("c3_depth_m") is not None:
        issues.append((19, "hard", "C3 belongs only to Open well / pond sources."))

    if a.get("source") == "open_ground" and a.get("c3g_depth_m") is None:
        issues.append((16, "hard", "Open ground water requires the C3G water-depth slider."))
    if a.get("source") != "open_ground" and a.get("c3g_depth_m") is not None:
        issues.append((19, "hard", "C3G belongs only to Open ground water sources."))

    # Boost cluster.
    if a.get("job") == "boost_pressure":
        if not a.get("c4_outlets"):
            issues.append((40, "hard", "Boost pressure requires C4 number of outlets."))
        if not a.get("c5_usage"):
            issues.append((40, "hard", "Boost pressure requires C5 simultaneous usage."))
        if not a.get("c5a_pressure"):
            issues.append((40, "hard", "Boost pressure requires C5a fixture / application pressure class."))
        if a.get("c5a_pressure") and a.get("setting") and a["c5a_pressure"] not in C5A_ALLOWED_BY_SETTING[a["setting"]]:
            issues.append((41, "hard", "C5a answer is not in the Setting-specific option set."))
        if a.get("setting") == "farm" and a.get("c5a_pressure") in FARM_OUTLET_ALLOWED and a.get("c4_outlets"):
            if a["c4_outlets"] not in FARM_OUTLET_ALLOWED[a["c5a_pressure"]]:
                issues.append((41, "hard", "C4 fixture count is not valid for the selected Farm pressure class."))
    else:
        for key_name in ("c4_outlets", "c5_usage", "c5a_pressure"):
            if a.get(key_name):
                issues.append((39, "hard", "C4, C5 and C5a belong only to Boost pressure."))
                break

    # Drain quality.
    if a.get("job") == "drain_sewage":
        if a.get("drain_quantity_l") is None:
            issues.append((45, "hard", "Drain sewage / water requires the quantity slider."))
        elif float(a.get("drain_quantity_l") or 0) <= 0:
            issues.append((45, "hard", "Drain quantity must be greater than zero."))
        if a.get("drain_time_h") is None:
            issues.append((45, "hard", "Drain sewage / water requires the time-to-clear slider."))
        elif float(a.get("drain_time_h") or 0) <= 0:
            issues.append((45, "hard", "Drain time must be greater than zero."))
        if not a.get("c6_quality"):
            issues.append((45, "hard", "Drain sewage / water requires C6 water quality / contents."))
        elif a["c6_quality"] not in C6_RULES:
            issues.append((47, "hard", "C6 answer is outside the defined option table."))
    elif a.get("c6_quality"):
        issues.append((46, "hard", "C6 water quality / contents belongs only to Drain sewage / water."))

    # Phase, duty, voltage.
    if a.get("setting"):
        if needs_phase_confirm(a) and not a.get("c7_phase"):
            issues.append((51, "hard", "C7 phase confirmation is required for this path."))
        if c8_triggered(a) and not a.get("c8_duty"):
            issues.append((52, "hard", "C8 duty cycle is required for this Setting or volume band."))
        if not c8_triggered(a) and a.get("c8_duty"):
            issues.append((53, "hard", "C8 was answered even though it is not triggered."))

        phase = final_phase(a) or default_phase(a["setting"])
        variant = c9_variant(a["setting"], phase)
        if variant == "single_band":
            if not a.get("c9_voltage_band"):
                issues.append((54, "hard", "C9 voltage at pump site is required."))
            elif a["c9_voltage_band"] not in {LOW_C9_BAND, NORMAL_C9_BAND}:
                issues.append((55, "hard", "Home / Shop-office single-phase C9 must use the two-band picker."))
            if a.get("c9_min_v") is not None or a.get("c9_max_v") is not None:
                issues.append((59, "hard", "C9 range values were supplied for a two-band single-phase case."))
        else:
            if a.get("c9_voltage_band"):
                issues.append((59, "hard", "C9 band answer was supplied for a Min/Max voltage case."))
            if a.get("c9_min_v") is None or a.get("c9_max_v") is None:
                issues.append((54, "hard", "C9 Min V and Max V are required."))
            else:
                mn, mx = int(a["c9_min_v"]), int(a["c9_max_v"])
                if mn >= mx:
                    issues.append((58 if phase == "Three" else 57, "hard", "C9 Min V must be less than Max V."))
                if variant == "farm_single_range":
                    if mn not in FARM_SINGLE_MIN_VALUES or mx not in FARM_SINGLE_MAX_VALUES:
                        issues.append((57, "hard", "Farm single-phase voltage range is outside the allowed dropdown values."))
                else:
                    if mn not in THREE_MIN_VALUES or mx not in THREE_MAX_VALUES:
                        issues.append((58, "hard", "Three-phase voltage range is outside the allowed dropdown values."))

    issues.extend(_soft_warnings(a))

    # Keep order stable and remove exact duplicates.
    seen = set()
    clean = []
    for item in issues:
        if item not in seen:
            clean.append(item)
            seen.add(item)
    return clean


def hard_errors(a: dict) -> list[str]:
    return [reason for _rid, sev, reason in evaluate(a) if sev == "hard"]


def soft_warnings(a: dict) -> list[str]:
    return [reason for _rid, sev, reason in evaluate(a) if sev == "soft"]
