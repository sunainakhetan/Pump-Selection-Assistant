"""
scoring.py — v0.6 hard-filter pipeline and midpoint scoring.
"""

import numpy as np
import pandas as pd


def _num(s):
    return pd.to_numeric(s, errors="coerce")


def _norm_str(s):
    return s.astype("string").str.strip()


def filter_skus(df: pd.DataFrame, vec: dict):
    trace = []
    work = df.copy()
    work["_cat_order"] = np.arange(len(work))
    trace.append({"step": "—", "label": "Start with all catalogue SKUs", "rows_left": len(work)})

    for col in ["Min Head (m)", "Max Head (m)", "Min Flow (LPH)", "Max Flow (LPH)", "HP"]:
        if col in work.columns:
            work[col] = _num(work[col])
    work = work.dropna(subset=["Min Head (m)", "Max Head (m)", "Min Flow (LPH)", "Max Flow (LPH)"])
    trace.append({"step": 1, "label": "Drop rows with non-numeric Min/Max Head or Min/Max Flow", "rows_left": len(work)})

    if not vec["allowed_pump_types"] or vec["special"].get("out_of_scope"):
        work = work.iloc[0:0]
        trace.append({"step": 2, "label": "Out of normal catalogue scope", "rows_left": 0})
        return work, trace

    work = work[work["Type"].isin(vec["allowed_pump_types"])]
    trace.append({"step": 2, "label": f"Keep only: {', '.join(vec['allowed_pump_types'])}", "rows_left": len(work)})

    work = work[work["Max Head (m)"] >= vec["required_min_head"]]
    trace.append({"step": 3, "label": f"Max Head ≥ {vec['required_min_head']} m", "rows_left": len(work)})

    work = work[work["Min Head (m)"] <= vec["typical_head"]]
    trace.append({"step": 4, "label": f"Min Head ≤ {vec['typical_head']} m", "rows_left": len(work)})

    work = work[work["Max Flow (LPH)"] >= vec["required_min_flow"]]
    trace.append({"step": 5, "label": f"Max Flow ≥ {vec['required_min_flow']:.0f} LPH", "rows_left": len(work)})

    work = work[work["Min Flow (LPH)"] <= vec["typical_flow"]]
    trace.append({"step": 6, "label": f"Min Flow ≤ {vec['typical_flow']:.0f} LPH", "rows_left": len(work)})

    # C1 borewell V-code filter.
    if "borewell_vcodes" in vec["special"]:
        codes = set(vec["special"]["borewell_vcodes"])
        is_bw = work["Type"] == "Borewell Pump"
        dia = _norm_str(work.get("Pump Diameter", pd.Series(index=work.index)))
        keep = (~is_bw) | dia.isin(codes)
        work = work[keep]
        trace.append({"step": 8, "label": f"Borewell Pump Diameter ∈ {{{', '.join(vec['special']['borewell_vcodes'])}}}", "rows_left": len(work)})

    phase = _norm_str(work.get("Phase", pd.Series(index=work.index, dtype="object")))
    phase_norm = phase.mask(phase.isna() | phase.eq("") | phase.str.lower().isin(["not found", "nan"]), pd.NA)

    # Revised fallback: borewell blank phase is treated as Three. Other blank rows
    # are lower-confidence fallbacks.
    borewell_blank = (work["Type"] == "Borewell Pump") & phase_norm.isna()
    phase_effective = phase_norm.mask(borewell_blank, "Three")
    work = work.assign(_phase_norm=phase_norm, _phase_effective=phase_effective)

    keep_known = work["_phase_effective"].isin(vec["allowed_phase"])
    keep_unknown = work["_phase_effective"].isna()
    work = work[keep_known | keep_unknown]
    trace.append({
        "step": 7,
        "label": f"Phase ∈ {{{', '.join(sorted(vec['allowed_phase']))}}}; blank borewell treated as Three, other blank kept as fallback",
        "rows_left": len(work),
    })

    # C9 voltage filter.
    variant = vec["special"].get("c9_variant")
    if variant == "single_band":
        vmin = _num(work.get("Single Phase Minimum Voltage", pd.Series(index=work.index)))
        vmax = _num(work.get("Single Phase Maximum Voltage", pd.Series(index=work.index)))
        band = vec["special"].get("c9_band")

        if band == "single_low_under_200":
            work = work[vmin.notna() & (vmin >= 180)]
            label = "C9 Low band: Single Phase Min V ≥ 180; unknown excluded"
        else:
            known_ok = vmin.notna() & (vmin >= 180)
            unknown = vmin.isna() | vmax.isna()
            work = work[known_ok | unknown]
            label = "C9 Normal band: known Single Phase Min V ≥ 180; unknown retained with confirm flag"

        trace.append({"step": "7a", "label": label, "rows_left": len(work)})

    elif variant == "farm_single_range":
        mn, mx = vec["special"].get("c9_min_v"), vec["special"].get("c9_max_v")
        vmin = _num(work.get("Single Phase Minimum Voltage", pd.Series(index=work.index)))
        vmax = _num(work.get("Single Phase Maximum Voltage", pd.Series(index=work.index)))
        work = work[vmin.notna() & vmax.notna() & (vmin >= mn) & (vmax <= mx)]
        trace.append({
            "step": "7a",
            "label": f"C9 Farm single-phase envelope inside [{mn}, {mx}] V; unknown excluded",
            "rows_left": len(work),
        })

    elif variant == "three_phase_range":
        mn, mx = vec["special"].get("c9_min_v"), vec["special"].get("c9_max_v")
        vmin = _num(work.get("Three Phase Minimum Voltage", pd.Series(index=work.index)))
        vmax = _num(work.get("Three Phase Maximum Voltage", pd.Series(index=work.index)))
        work = work[vmin.notna() & vmax.notna() & (vmin >= mn) & (vmax <= mx)]
        trace.append({
            "step": "7a",
            "label": f"C9 Three-phase envelope inside [{mn}, {mx}] V; unknown excluded",
            "rows_left": len(work),
        })

    if "suction_lift_required" in vec["special"]:
        req = vec["special"]["suction_lift_required"]
        is_sp = work["Type"] == "Self-Priming Pump"
        sl = _num(work.get("Suction Lift (m)", pd.Series(index=work.index)))
        work = work[(~is_sp) | (sl >= req) | sl.isna()]
        trace.append({
            "step": 9,
            "label": f"Self-Priming suction lift ≥ {req} m (unknown kept with penalty)",
            "rows_left": len(work),
        })

    if "self_priming_rpm_max" in vec["special"]:
        limit = vec["special"]["self_priming_rpm_max"]
        is_sp = work["Type"] == "Self-Priming Pump"
        rpm = _num(work.get("Speed (RPM)", pd.Series(index=work.index)))
        work = work[(~is_sp) | (rpm.notna() & (rpm < limit))]
        trace.append({
            "step": 10,
            "label": f"Lightly soiled: keep Self-Priming Speed < {limit} RPM; unknown excluded",
            "rows_left": len(work),
        })

    if "cutter_required" in vec["special"]:
        req = vec["special"]["cutter_required"]
        is_sew = work["Type"] == "Sewage Pump"
        cutter = _norm_str(work.get("Cutter Type", pd.Series(index=work.index))).str.lower()
        work = work[(~is_sew) | (cutter == req.lower())]
        trace.append({"step": 11, "label": f"Sewage Cutter Type = '{req}'", "rows_left": len(work)})

    if vec.get("hp_cap") is not None:
        cap = vec["hp_cap"]
        hp = _num(work.get("HP", pd.Series(index=work.index)))
        work = work[hp.notna() & (hp <= 2 * cap)]
        trace.append({
            "step": 13,
            "label": f"HP ≤ {2 * cap} (2× preferred {cap} HP cap)",
            "rows_left": len(work),
        })
    else:
        trace.append({"step": 13, "label": "HP hard cap skipped for this setting", "rows_left": len(work)})

    return work, trace


def _safe(numerator, denominator):
    if denominator is None or denominator <= 0 or pd.isna(denominator):
        return 0.0
    return max(0.0, min(1.0, 1.0 - abs(numerator) / denominator))


def _voltage_bonus(row, vec):
    special = vec["special"]
    variant = special.get("c9_variant")
    bonus = 0.0
    flags = []

    if variant == "single_band":
        vmin = pd.to_numeric(row.get("Single Phase Minimum Voltage"), errors="coerce")
        vmax = pd.to_numeric(row.get("Single Phase Maximum Voltage"), errors="coerce")

        if pd.isna(vmin) or pd.isna(vmax):
            if special.get("c9_band") == "single_normal_200_240":
                flags.append("confirm_voltage")
            return bonus, flags

        if special.get("c9_band") == "single_low_under_200":
            # Best around 180–185 V; slight negative tilt for higher min voltage.
            bonus -= min(4.0, max(0.0, (vmin - 185) / 10.0))
        else:
            if vmin >= 200 and vmax <= 240:
                bonus += 2.0
            elif 180 <= vmin < 200:
                bonus -= 2.0

    elif variant in {"farm_single_range", "three_phase_range"}:
        # Range variants are already hard-filtered. Keep scoring hydraulic-only.
        bonus += 0.0

    return bonus, flags


def score_skus(df: pd.DataFrame, vec: dict):
    if len(df) == 0:
        return df.assign(score=pd.Series(dtype=float))

    typ_h = vec["typical_head"]
    typ_f = vec["typical_flow"]
    hp_cap = vec.get("hp_cap")
    rows = []

    for _, r in df.iterrows():
        min_h, max_h = r["Min Head (m)"], r["Max Head (m)"]
        min_f, max_f = r["Min Flow (LPH)"], r["Max Flow (LPH)"]

        head_mid = (min_h + max_h) / 2
        flow_mid = (min_f + max_f) / 2

        head_score = _safe(typ_h - head_mid, max_h - min_h)
        flow_score = _safe(typ_f - flow_mid, max_f - min_f)

        penalties = 0.0
        bonus = 0.0
        flags = []

        hp = pd.to_numeric(r.get("HP"), errors="coerce")
        if hp_cap is not None and pd.notna(hp) and hp > hp_cap:
            penalties += min(15, (hp - hp_cap) * 3)

        if pd.isna(r.get("_phase_norm")):
            penalties += 8
            flags.append("confirm_phase_before_purchase")

        if (
            vec["special"].get("suction_lift_required") is not None
            and r.get("Type") == "Self-Priming Pump"
            and pd.isna(pd.to_numeric(r.get("Suction Lift (m)"), errors="coerce"))
        ):
            penalties += 5
            flags.append("suction_lift_unknown")

        rpm = pd.to_numeric(r.get("Speed (RPM)"), errors="coerce")
        if r.get("Type") == "Self-Priming Pump":
            if pd.isna(rpm):
                flags.append("speed_unknown_selfpriming")
            elif vec.get("run_hours", 0) >= 6:
                # Long duty: slow-speed is preferred.
                if rpm < 1500:
                    bonus += 1.5
                else:
                    bonus -= 1.5
            elif vec["special"].get("c9_variant"):
                # Short/normal clean-water duty: high-speed self-priming is preferred.
                if rpm >= 1500:
                    bonus += 1.0

        if vec["special"].get("prefer_slim_v3") and str(r.get("Pump Diameter")) == "V3":
            v3_type = str(r.get("V3 Type", "")).strip().lower()
            if v3_type == "slim v3":
                bonus += 1.5
            elif v3_type in {"not found", "", "nan"}:
                flags.append("confirm_v3_fitment")

        vb, vf = _voltage_bonus(r, vec)
        bonus += vb
        flags.extend(vf)

        if vec.get("run_hours") == 14 and str(r.get("Cooling Type", "")).lower() == "water-cooled":
            bonus += 1.0

        final = round(60 * head_score + 40 * flow_score + bonus - penalties)

        rows.append({
            "score": final,
            "head_score": round(head_score, 4),
            "flow_score": round(flow_score, 4),
            "bonus": round(bonus, 2),
            "penalties": round(penalties, 2),
            "flags": list(dict.fromkeys(flags)),
        })

    extra = pd.DataFrame(rows, index=df.index)
    out = pd.concat([df, extra], axis=1)
    out = out.sort_values(["score", "_cat_order"], ascending=[False, True], kind="mergesort")
    return out


def lift_flags(ans: dict):
    flags = []
    lift = ans.get("lift")

    if lift == "floors_16_25":
        flags.append(("staged_pumping_recommended", "High-rise: staged pumping is normally recommended at 16–25 floors."))

    if lift == "floors_26_40":
        flags.append(("multi_zone_booster_required", "Multi-zone booster scheme typically required at 26–40 floors."))

    if lift == "floors_41_60":
        flags.append(("consultant_review_recommended", "Consultant review recommended for 41–60 floor schemes."))

    if lift == "floors_above_60":
        flags.append(("custom_engineering_required", "Above 60 floors normally requires custom engineering."))

    if ans.get("c6_quality") == "industrial_effluent":
        flags.append(("custom_engineering_required", "Industrial effluent is outside normal catalogue scope."))

    return flags
