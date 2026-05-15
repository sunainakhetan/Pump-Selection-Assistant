"""
scoring.py — 12-step hard-filter pipeline and midpoint scoring.

Filter order is taken verbatim from FILTERING_AND_SCORING_MECHANISM doc §5.
Scoring formulas are taken verbatim from §7.

Inputs:
  df  — a pandas DataFrame containing the `Master Data` sheet of the Excel.
  vec — a requirement-vector dict produced by vector.build_vector(...).

Output:
  ranked_df : DataFrame of survivors, sorted by `score` descending (catalogue
              order preserved on ties — pandas' default mergesort is stable).
  trace     : list of dicts {step, label, rows_left} describing each filter
              step, used for the worked-example verification + transparency UI.
"""

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Filter pipeline
# ---------------------------------------------------------------------------

def filter_skus(df: pd.DataFrame, vec: dict):
    trace = []
    work = df.copy()
    # Preserve catalogue order for stable tie-breaking
    work["_cat_order"] = np.arange(len(work))
    trace.append({"step": 1, "label": "Start with all catalogue SKUs", "rows_left": len(work)})

    # Step 1: SKU usable (Min/Max head and flow numeric)
    for col in ["Min Head (m)", "Max Head (m)", "Min Flow (LPH)", "Max Flow (LPH)"]:
        work[col] = pd.to_numeric(work[col], errors="coerce")
    work = work.dropna(subset=["Min Head (m)", "Max Head (m)", "Min Flow (LPH)", "Max Flow (LPH)"])
    trace.append({"step": 1, "label": "Drop rows with non-numeric head/flow", "rows_left": len(work)})

    # Step 2: Pump type filter
    if not vec["allowed_pump_types"]:
        # out-of-scope (e.g. industrial effluent) → nothing matches
        work = work.iloc[0:0]
        trace.append({"step": 2, "label": "Pump type filter (out of scope)", "rows_left": 0})
        return work, trace
    work = work[work["Type"].isin(vec["allowed_pump_types"])]
    trace.append({"step": 2, "label": f"Keep only: {', '.join(vec['allowed_pump_types'])}", "rows_left": len(work)})

    # Step 3: SKU Max Head >= Required Minimum Head
    work = work[work["Max Head (m)"] >= vec["required_min_head"]]
    trace.append({"step": 3, "label": f"Max Head ≥ {vec['required_min_head']} m", "rows_left": len(work)})

    # Step 4: SKU Min Head <= Typical Head (upper-edge head)
    work = work[work["Min Head (m)"] <= vec["typical_head"]]
    trace.append({"step": 4, "label": f"Min Head ≤ {vec['typical_head']} m", "rows_left": len(work)})

    # Step 5: SKU Max Flow >= Required Minimum Flow
    work = work[work["Max Flow (LPH)"] >= vec["required_min_flow"]]
    trace.append({"step": 5, "label": f"Max Flow ≥ {vec['required_min_flow']:.0f} LPH", "rows_left": len(work)})

    # Step 6: SKU Min Flow <= Typical Flow (upper-edge flow)
    work = work[work["Min Flow (LPH)"] <= vec["typical_flow"]]
    trace.append({"step": 6, "label": f"Min Flow ≤ {vec['typical_flow']:.0f} LPH", "rows_left": len(work)})

    # Step 7: Phase filter. Known incompatible phase removed.
    # Blank/N/A phase kept as fallback with a confidence penalty (applied later).
    allowed = vec["allowed_phase"]  # set like {"Single","Both"} or {"Three","Both"}
    # Normalise phase column: treat "Not Found" and NaN as Unknown.
    phase = work["Phase"].astype("string")
    phase_norm = phase.where(~phase.isin(["Not Found"]), other=pd.NA)
    work = work.assign(_phase_norm=phase_norm)

    keep_phase = work["_phase_norm"].isin(allowed)
    keep_unknown = work["_phase_norm"].isna()  # fallback
    work = work[keep_phase | keep_unknown]
    trace.append({"step": 7, "label": f"Phase ∈ {{{', '.join(sorted(allowed))}}} (blank kept as fallback)",
                  "rows_left": len(work)})

    # Step 7a: C9 voltage filter (single-phase only)
    if vec.get("final_phase") == "Single" and "c9_voltage" in vec["special"]:
        band = vec["special"]["c9_voltage"]
        v = pd.to_numeric(work["Single Phase Minimum Voltage"], errors="coerce")
        if band == "very_low":
            work = work[v.notna() & (v < 180)]
            trace.append({"step": "7a", "label": "C9 Very low: Single Phase Min V < 180", "rows_left": len(work)})
        elif band == "low":
            work = work[v.notna() & (v < 200)]
            trace.append({"step": "7a", "label": "C9 Low: Single Phase Min V < 200", "rows_left": len(work)})
        else:
            # Normal voltage adds no extra constraint
            trace.append({"step": "7a", "label": "C9 Normal: no additional constraint",
                          "rows_left": len(work)})

    # Step 8: Borewell diameter filter
    if "borewell_vcodes" in vec["special"]:
        codes = vec["special"]["borewell_vcodes"]
        is_bw = work["Type"] == "Borewell Pump"
        # For borewell rows, keep only matching V-codes.
        # For non-borewell rows in mixed candidate sets, the filter does not apply.
        keep = (~is_bw) | (work["Pump Diameter"].astype("string").isin(codes))
        work = work[keep]
        trace.append({"step": 8, "label": f"Borewell V-codes ∈ {{{', '.join(codes)}}}",
                      "rows_left": len(work)})

    # Step 9: Suction-lift filter (Self-Priming rows only).
    # Per the doc, suction-lift unknown gets a soft penalty later, not removal.
    if "suction_lift_required" in vec["special"]:
        req = vec["special"]["suction_lift_required"]
        is_sp = work["Type"] == "Self-Priming Pump"
        sl = pd.to_numeric(work["Suction Lift (m)"], errors="coerce")
        # SP rows: must have suction_lift >= req OR be unknown (kept with penalty)
        keep_sp = (sl >= req) | sl.isna()
        keep = (~is_sp) | keep_sp
        work = work[keep]
        trace.append({"step": 9, "label": f"Self-Priming suction lift ≥ {req} m (or unknown w/ penalty)",
                      "rows_left": len(work)})

    # Step 10: Cutter filter (Sewage only)
    if "cutter_required" in vec["special"]:
        req = vec["special"]["cutter_required"]
        is_sew = work["Type"] == "Sewage Pump"
        ct = work["Cutter Type"].astype("string").str.strip().str.lower()
        keep = (~is_sew) | (ct == req.lower())
        work = work[keep]
        trace.append({"step": 10, "label": f"Sewage Cutter Type = '{req}'",
                      "rows_left": len(work)})

    # Step 11: Out-of-scope blocker (industrial effluent etc.) already returned at step 2.

    # Step 12: HP hard cap (only when a preferred cap is set)
    if vec.get("hp_cap") is not None:
        cap = vec["hp_cap"]
        hp = pd.to_numeric(work["HP"], errors="coerce")
        work = work[hp.notna() & (hp <= 2 * cap)]
        trace.append({"step": 12, "label": f"HP ≤ {2 * cap} (2× preferred {cap} HP cap)",
                      "rows_left": len(work)})

    return work, trace


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _safe(numerator, denominator):
    """1 - |numerator|/denominator, clipped to [0,1]. Zero denom → 0."""
    if denominator is None or denominator <= 0 or pd.isna(denominator):
        return 0.0
    return max(0.0, min(1.0, 1.0 - abs(numerator) / denominator))


def score_skus(df: pd.DataFrame, vec: dict):
    """Score the survivors. Returns a sorted DataFrame with extra columns."""
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
        flags = []

        # HP soft penalty in the 1× to 2× preferred cap range
        hp = float(r["HP"]) if pd.notna(r["HP"]) else None
        if hp_cap is not None and hp is not None and hp > hp_cap:
            penalties += min(15, (hp - hp_cap) * 3)

        # Phase penalty for unknown phase rows kept as fallback
        phase = r.get("_phase_norm")
        if pd.isna(phase):
            penalties += 8
            flags.append("confirm_phase_before_purchase")

        # Suction-lift unknown penalty (Self-Priming rows)
        if vec["special"].get("suction_lift_required") is not None \
           and r["Type"] == "Self-Priming Pump" \
           and pd.isna(pd.to_numeric(r["Suction Lift (m)"], errors="coerce")):
            penalties += 5
            flags.append("suction_lift_unknown")

        final = round(60 * head_score + 40 * flow_score - penalties)

        rows.append({
            "score": final,
            "head_score": round(head_score, 4),
            "flow_score": round(flow_score, 4),
            "penalties": round(penalties, 2),
            "flags": flags,
        })

    extra = pd.DataFrame(rows, index=df.index)
    out = pd.concat([df, extra], axis=1)
    out = out.sort_values(["score", "_cat_order"], ascending=[False, True], kind="mergesort")
    return out


# ---------------------------------------------------------------------------
# Lift-based informational flags (independent of scoring)
# ---------------------------------------------------------------------------

def lift_flags(ans: dict):
    """Return informational flags based on the Lift answer."""
    flags = []
    lift = ans.get("lift")
    if lift == "floors_16_25":
        flags.append(("staged_pumping_recommended",
                      "High-rise: staged pumping is the real-world norm at 16–25 floors."))
    if lift == "floors_26_40":
        flags.append(("multi_zone_booster_required",
                      "Multi-zone booster scheme typically required at 26–40 floors."))
    if lift == "floors_41_60":
        flags.append(("consultant_review_recommended",
                      "Consultant review recommended for 41–60 floor schemes."))
    if lift == "floors_above_60":
        flags.append(("custom_engineering_required",
                      "Above 60 floors normally requires custom engineering."))
    return flags
