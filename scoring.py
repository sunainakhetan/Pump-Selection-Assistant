"""
scoring.py — v1.1 hard-filter pipeline and midpoint ranking.

The catalogue has Min/Max Head and Min/Max Flow ranges rather than full pump
curves, so ranking uses the framework's midpoint approximation: hydraulic fit
first, then small penalties/tilts for HP, phase unknowns, suction uncertainty,
voltage robustness, Self-Priming speed, and municipal-path conservatism.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

NA_STRINGS = {"", "n/a", "na", "nan", "none", "not found", "not_found", "-", "--", "n.a.", "not available"}


def _series(index, dtype="object"):
    return pd.Series(index=index, dtype=dtype)


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def _norm_str(s: pd.Series) -> pd.Series:
    out = s.astype("string").str.strip()
    return out.mask(out.isna() | out.str.lower().isin(NA_STRINGS), pd.NA)


def _norm_lower(s: pd.Series) -> pd.Series:
    return _norm_str(s).str.lower()


def _column(df: pd.DataFrame, name: str, dtype="object") -> pd.Series:
    return df[name] if name in df.columns else _series(df.index, dtype=dtype)


def _trace(trace, step, label, work):
    trace.append({"step": step, "label": label, "rows_left": int(len(work))})


def filter_skus(df: pd.DataFrame, vec: dict):
    """Apply the ordered v1.1 hard filters and return (survivors, trace)."""

    trace = []
    work = df.copy()
    work["_cat_order"] = np.arange(len(work))
    _trace(trace, "—", "Start with all catalogue SKUs", work)

    numeric_cols = [
        "Min Head (m)",
        "Max Head (m)",
        "Min Flow (LPH)",
        "Max Flow (LPH)",
        "HP",
        "Suction Lift (m)",
        "Speed (RPM)",
        "Single Phase Minimum Voltage",
        "Single Phase Maximum Voltage",
        "Three Phase Minimum Voltage",
        "Three Phase Maximum Voltage",
        "Minimum Pressure (bar)",
        "Maximum Pressure (bar)",
    ]
    for col in numeric_cols:
        if col in work.columns:
            work[col] = _num(work[col])

    required_perf = ["Min Head (m)", "Max Head (m)", "Min Flow (LPH)", "Max Flow (LPH)"]
    work = work.dropna(subset=[c for c in required_perf if c in work.columns])
    _trace(trace, 1, "Drop rows with non-numeric Min/Max Head or Min/Max Flow", work)

    allowed = vec.get("allowed_pump_types", [])
    if not allowed or vec.get("special", {}).get("out_of_scope"):
        work = work.iloc[0:0]
        _trace(trace, 2, "Out of enabled v1.1 matrix scope", work)
        return work, trace

    work = work[work["Type"].isin(allowed)]
    _trace(trace, 2, f"Keep matrix-cell pump types: {', '.join(allowed)}", work)

    req_head = float(vec.get("required_min_head", 0))
    typ_head = float(vec.get("typical_head", 0))
    req_flow = float(vec.get("required_min_flow", 0))
    typ_flow = float(vec.get("typical_flow", 0))

    work = work[work["Max Head (m)"] >= req_head]
    _trace(trace, 3, f"Max Head ≥ {req_head:.2f} m", work)

    work = work[work["Min Head (m)"] <= typ_head]
    _trace(trace, 4, f"Min Head ≤ {typ_head:.2f} m", work)

    work = work[work["Max Flow (LPH)"] >= req_flow]
    _trace(trace, 5, f"Max Flow ≥ {req_flow:.0f} LPH", work)

    work = work[work["Min Flow (LPH)"] <= typ_flow]
    _trace(trace, 6, f"Min Flow ≤ {typ_flow:.0f} LPH", work)

    # Phase filter. Blank/Not Found borewell is treated as Three by fallback;
    # other blank phase rows are retained as lower-confidence fallbacks.
    phase_norm = _norm_str(_column(work, "Phase"))
    borewell_blank = (work["Type"] == "Borewell Pump") & phase_norm.isna()
    phase_effective = phase_norm.mask(borewell_blank, "Three")
    work = work.assign(_phase_norm=phase_norm, _phase_effective=phase_effective)

    allowed_phase = set(vec.get("allowed_phase", set()))
    keep_known = work["_phase_effective"].isin(allowed_phase)
    keep_unknown = work["_phase_effective"].isna()
    work = work[keep_known | keep_unknown]
    _trace(
        trace,
        7,
        f"Phase ∈ {{{', '.join(sorted(allowed_phase))}}}; blank borewell treated as Three; other blank retained as fallback",
        work,
    )

    # Corrected v1.1 voltage filter.
    special = vec.get("special", {})
    variant = special.get("c9_variant")
    if variant == "single_band":
        vmin = _num(_column(work, "Single Phase Minimum Voltage"))
        vmax = _num(_column(work, "Single Phase Maximum Voltage"))
        band = special.get("c9_band")
        if band == "single_low_under_200":
            work = work[vmin.notna() & (vmin >= 180)]
            label = "C9 low-voltage single-phase: Single Phase Min V ≥ 180; unknown excluded"
        else:
            known_ok = vmin.notna() & (vmin >= 180)
            unknown = vmin.isna() | vmax.isna()
            work = work[known_ok | unknown]
            label = "C9 normal single-phase: known Single Phase Min V ≥ 180; unknown retained with confirm-voltage flag"
        _trace(trace, "7a", label, work)

    elif variant == "farm_single_range":
        mn, mx = special.get("c9_min_v"), special.get("c9_max_v")
        vmin = _num(_column(work, "Single Phase Minimum Voltage"))
        vmax = _num(_column(work, "Single Phase Maximum Voltage"))
        work = work[vmin.notna() & vmax.notna() & (vmin <= mn) & (vmax >= mx)]
        _trace(trace, "7a", f"C9 Farm single-phase contain-test: pump min_v ≤ {mn} AND pump max_v ≥ {mx}; unknown excluded", work)

    elif variant == "three_phase_range":
        mn, mx = special.get("c9_min_v"), special.get("c9_max_v")
        vmin = _num(_column(work, "Three Phase Minimum Voltage"))
        vmax = _num(_column(work, "Three Phase Maximum Voltage"))
        work = work[vmin.notna() & vmax.notna() & (vmin <= mn) & (vmax >= mx)]
        _trace(trace, "7a", f"C9 Three-phase contain-test: pump min_v ≤ {mn} AND pump max_v ≥ {mx}; unknown excluded", work)

    # C1 borewell V-code filter.
    if "borewell_vcodes" in special:
        codes = set(special["borewell_vcodes"])
        dia = _norm_str(_column(work, "Pump Diameter"))
        is_bw = work["Type"] == "Borewell Pump"
        if "casing_12in_plus" in str(special.get("borewell_casing", "")):
            keep_dia = dia.apply(_vcode_is_12_plus)
        else:
            keep_dia = dia.isin(codes)
        work = work[(~is_bw) | keep_dia]
        _trace(trace, 8, f"Borewell Pump Diameter ∈ {{{', '.join(special['borewell_vcodes'])}}}", work)

    # Open-ground-water ≤ 7 m suction-lift rule.
    if "suction_lift_required" in special:
        req = float(special["suction_lift_required"])
        is_sp = work["Type"] == "Self-Priming Pump"
        suction = _num(_column(work, "Suction Lift (m)"))
        work = work[(~is_sp) | suction.isna() | (suction >= req)]
        _trace(trace, 9, f"Self-Priming Suction Lift ≥ {req:.1f} m for open ground water ≤ 7 m; unknown kept with penalty", work)

    # Drain C6 cutter / non-cutter requirement.
    if "cutter_required" in special:
        req = str(special["cutter_required"]).lower().strip()
        is_sew = work["Type"] == "Sewage Pump"
        cutter = _norm_lower(_column(work, "Cutter Type"))
        work = work[(~is_sew) | (cutter == req)]
        _trace(trace, 10, f"Sewage Cutter Type = '{req}'", work)

    # Setting HP hard cap: Home / Shop-office preferred cap is 3 HP, hard ceiling 6 HP.
    hp_cap = vec.get("hp_cap")
    if hp_cap is not None:
        hp = _num(_column(work, "HP"))
        work = work[hp.isna() | (hp <= 2 * hp_cap)]
        _trace(trace, 11, f"HP ≤ {2 * hp_cap} where HP is known (2× preferred {hp_cap} HP cap)", work)
    else:
        _trace(trace, 11, "HP hard cap skipped for this Setting", work)

    return work, trace


def _vcode_is_12_plus(value: Any) -> bool:
    if value is None or pd.isna(value):
        return False
    text = str(value).strip().upper().replace("V", "")
    try:
        return float(text) >= 12
    except Exception:
        return False


def _safe_score(target: float, minimum: float, maximum: float) -> float:
    width = maximum - minimum
    if not np.isfinite(width) or width <= 0:
        return 0.0
    midpoint = (minimum + maximum) / 2.0
    return max(0.0, min(1.0, 1.0 - abs(target - midpoint) / width))


def _voltage_rank_and_flags(row: pd.Series, vec: dict) -> tuple[float, list[str]]:
    special = vec.get("special", {})
    variant = special.get("c9_variant")
    flags: list[str] = []
    rank = 0.0

    if variant == "single_band":
        vmin = pd.to_numeric(row.get("Single Phase Minimum Voltage"), errors="coerce")
        vmax = pd.to_numeric(row.get("Single Phase Maximum Voltage"), errors="coerce")
        if pd.isna(vmin) or pd.isna(vmax):
            if special.get("c9_band") == "single_normal_200_240":
                flags.append("confirm_voltage")
            return -1.0, flags
        if special.get("c9_band") == "single_low_under_200":
            # Best sag tolerance is a min voltage close to the 180–185 V floor.
            rank = -abs(float(vmin) - 182.5)
        else:
            if float(vmin) >= 200 and float(vmax) <= 240:
                rank = 2.0
            elif 180 <= float(vmin) < 200:
                rank = 0.5
            else:
                rank = 0.0

    elif variant == "farm_single_range":
        site_min = special.get("c9_min_v")
        site_max = special.get("c9_max_v")
        vmin = pd.to_numeric(row.get("Single Phase Minimum Voltage"), errors="coerce")
        vmax = pd.to_numeric(row.get("Single Phase Maximum Voltage"), errors="coerce")
        if pd.notna(vmin) and pd.notna(vmax) and site_min is not None and site_max is not None:
            rank = float(site_min - vmin) + float(vmax - site_max)

    elif variant == "three_phase_range":
        site_min = special.get("c9_min_v")
        site_max = special.get("c9_max_v")
        vmin = pd.to_numeric(row.get("Three Phase Minimum Voltage"), errors="coerce")
        vmax = pd.to_numeric(row.get("Three Phase Maximum Voltage"), errors="coerce")
        if pd.notna(vmin) and pd.notna(vmax) and site_min is not None and site_max is not None:
            rank = float(site_min - vmin) + float(vmax - site_max)

    return rank, flags


def _speed_rank_and_flags(row: pd.Series, vec: dict) -> tuple[float, list[str]]:
    flags: list[str] = []
    if row.get("Type") != "Self-Priming Pump":
        return 0.0, flags

    rpm = pd.to_numeric(row.get("Speed (RPM)"), errors="coerce")
    water_scarce = bool(vec.get("special", {}).get("water_scarce"))
    if water_scarce:
        flags.append("water_scarcity_slow_speed_advisory")

    if pd.isna(rpm):
        flags.append("speed_unknown_selfpriming")
        return -1.0, flags

    is_slow = float(rpm) < 1500
    if water_scarce:
        return (2.0 if is_slow else 0.5), flags
    return (2.0 if not is_slow else 0.5), flags


def _row_flags_from_vector(vec: dict) -> list[str]:
    return list(vec.get("warnings", []))


def score_skus(df: pd.DataFrame, vec: dict):
    """Score survivors using the v1.1 midpoint method and stable tie-breakers."""

    if len(df) == 0:
        return df.assign(score=pd.Series(dtype=float), flags=pd.Series(dtype=object))

    typ_h = float(vec["typical_head"])
    typ_f = float(vec["typical_flow"])
    hp_cap = vec.get("hp_cap")
    base_vector_flags = _row_flags_from_vector(vec)
    rows = []

    for _, r in df.iterrows():
        min_h, max_h = float(r["Min Head (m)"]), float(r["Max Head (m)"])
        min_f, max_f = float(r["Min Flow (LPH)"]), float(r["Max Flow (LPH)"])

        head_score = _safe_score(typ_h, min_h, max_h)
        flow_score = _safe_score(typ_f, min_f, max_f)

        penalties = 0.0
        bonus = 0.0
        flags = list(base_vector_flags)

        hp = pd.to_numeric(r.get("HP"), errors="coerce")
        if hp_cap is not None and pd.notna(hp) and hp > hp_cap:
            penalties += min(15.0, float(hp - hp_cap) * 3.0)

        if pd.isna(r.get("_phase_norm")):
            penalties += 8.0
            flags.append("confirm_phase_before_purchase")

        if (
            vec.get("special", {}).get("suction_lift_required") is not None
            and r.get("Type") == "Self-Priming Pump"
            and pd.isna(pd.to_numeric(r.get("Suction Lift (m)"), errors="coerce"))
        ):
            penalties += 5.0
            flags.append("suction_lift_unknown")

        voltage_rank, voltage_flags = _voltage_rank_and_flags(r, vec)
        flags.extend(voltage_flags)

        speed_rank, speed_flags = _speed_rank_and_flags(r, vec)
        flags.extend(speed_flags)

        if vec.get("special", {}).get("municipal_path") and r.get("Type") == "Self-Priming Pump":
            flags.append("municipal_marginal_pressure")
            municipal_rank = -1.0
        else:
            municipal_rank = 0.0

        # Very small cooling signal for continuous duty. Kept deliberately small.
        cooling = str(r.get("Cooling Type", "")).strip().lower()
        if vec.get("run_hours") == 14 and cooling and cooling not in NA_STRINGS:
            bonus += 1.0

        final = max(0, round(60 * head_score + 40 * flow_score + bonus - penalties))
        rows.append(
            {
                "score": final,
                "head_score": round(head_score, 4),
                "flow_score": round(flow_score, 4),
                "bonus": round(bonus, 2),
                "penalties": round(penalties, 2),
                "flags": list(dict.fromkeys(flags)),
                "_voltage_rank": round(float(voltage_rank), 4),
                "_speed_rank": round(float(speed_rank), 4),
                "_municipal_rank": round(float(municipal_rank), 4),
            }
        )

    extra = pd.DataFrame(rows, index=df.index)
    out = pd.concat([df, extra], axis=1)

    sort_cols = ["score", "_voltage_rank", "_speed_rank", "_municipal_rank"]
    ascending = [False, False, False, False]
    if "HP" in out.columns:
        out["_hp_sort"] = pd.to_numeric(out["HP"], errors="coerce").fillna(float("inf"))
        sort_cols.append("_hp_sort")
        ascending.append(True)
    sort_cols.append("_cat_order")
    ascending.append(True)

    return out.sort_values(sort_cols, ascending=ascending, kind="mergesort")


def _lift_floor_count(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return max(0.0, float(value))
    legacy = {
        "ground": 0,
        "floor_1": 1,
        "floor_2": 2,
        "floor_3": 3,
        "floor_4": 4,
        "floors_5_10": 10,
        "floors_11_15": 15,
        "floors_16_25": 25,
        "floors_26_40": 40,
        "floors_41_60": 60,
        "floors_above_60": 60,
    }
    text = str(value).strip()
    if text.replace(".", "", 1).isdigit():
        return max(0.0, float(text))
    return float(legacy.get(text, 0))


def lift_flags(ans: dict) -> list[tuple[str, str]]:
    flags = []
    floors = _lift_floor_count(ans.get("lift"))
    if 16 <= floors <= 25:
        flags.append(("staged_pumping_recommended", "High-rise: staged pumping is normally recommended for 16–25 floors."))
    elif 26 <= floors <= 40:
        flags.append(("multi_zone_booster_required", "Multi-zone booster scheme is typically used for 26–40 floors."))
    elif floors >= 41:
        flags.append(("consultant_review_recommended", "Consultant review is recommended for 41+ floor schemes."))
    if ans.get("drain_rate") == "industrial_large":
        flags.append(("custom_engineering_required", "Industrial / large-scale dewatering usually needs a multi-pump or consultant design."))
    if ans.get("water_scarce"):
        flags.append(("water_scarcity_slow_speed_advisory", "For intermittent or water-scarce supply, slow-speed self-priming options are prioritised where suitable."))
    return flags
