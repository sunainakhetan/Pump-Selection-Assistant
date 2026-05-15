"""
app.py — Pump Selection Assistant (Streamlit)

A step-by-step questionnaire that converts customer answers into a
requirement vector, filters the 4,020-row SKU catalogue per the documented
rules, scores survivors by midpoint match, and returns polished
recommendation cards.

Catalogue source-of-truth: FINAL_MASTER_DATASHEET_final.xlsx (Master Data sheet).
Rules source-of-truth: Pump_UseCase_Framework + FILTERING_AND_SCORING_MECHANISM docs.
"""

import os
from pathlib import Path

import pandas as pd
import streamlit as st

from rules import evaluate, is_disabled
from scoring import filter_skus, score_skus, lift_flags
from vector import build_vector

# ---------------------------------------------------------------------------
# Page config & catalogue loader
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Pump Selection Assistant",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="collapsed",
)

EXCEL_PATH = Path(__file__).parent / "FINAL_MASTER_DATASHEET_final.xlsx"


@st.cache_data(show_spinner=False)
def load_catalogue(path: str, mtime: float) -> pd.DataFrame:
    """Read the Master Data sheet. `mtime` is in the cache key so edits
    to the Excel file invalidate the cache automatically."""
    return pd.read_excel(path, sheet_name="Master Data")


def get_catalogue() -> pd.DataFrame:
    mtime = os.path.getmtime(EXCEL_PATH) if EXCEL_PATH.exists() else 0
    return load_catalogue(str(EXCEL_PATH), mtime)


# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------

CSS = """
<style>
:root {
  --teal: #0d9488;
  --teal-dark: #0f766e;
  --teal-light: #ccfbf1;
  --blue: #1e40af;
  --ink: #0f172a;
  --muted: #64748b;
  --bg: #f8fafc;
  --card: #ffffff;
  --amber-bg: #fef3c7;
  --amber-border: #f59e0b;
  --amber-ink: #92400e;
  --red-bg: #fee2e2;
  --red-border: #ef4444;
  --red-ink: #991b1b;
}
html, body, [class*="css"] {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}
.block-container { padding-top: 2rem; padding-bottom: 4rem; max-width: 1100px; }
h1, h2, h3 { color: var(--ink); letter-spacing: -0.01em; }
.hero {
  background: linear-gradient(135deg, var(--teal) 0%, var(--blue) 100%);
  border-radius: 16px;
  padding: 28px 32px;
  margin-bottom: 28px;
  color: white;
  box-shadow: 0 10px 25px -10px rgba(13, 148, 136, 0.45);
}
.hero h1 { color: white; margin: 0 0 6px 0; font-size: 1.8rem; }
.hero p { color: rgba(255,255,255,0.92); margin: 0; font-size: 0.98rem; }

.step-badge {
  display: inline-block;
  background: var(--teal-light);
  color: var(--teal-dark);
  font-size: 0.78rem;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 999px;
  margin-bottom: 6px;
  letter-spacing: 0.02em;
}
.section-title { font-size: 1.1rem; font-weight: 600; color: var(--ink); margin: 4px 0 2px; }
.section-help  { font-size: 0.88rem; color: var(--muted); margin-bottom: 12px; }

.warning-box {
  background: var(--amber-bg);
  border-left: 4px solid var(--amber-border);
  color: var(--amber-ink);
  padding: 10px 14px;
  border-radius: 8px;
  margin: 10px 0;
  font-size: 0.92rem;
}
.error-box {
  background: var(--red-bg);
  border-left: 4px solid var(--red-border);
  color: var(--red-ink);
  padding: 10px 14px;
  border-radius: 8px;
  margin: 10px 0;
  font-size: 0.92rem;
}

.rec-card {
  background: var(--card);
  border-radius: 14px;
  padding: 20px 22px;
  margin-bottom: 16px;
  box-shadow: 0 4px 16px -6px rgba(15, 23, 42, 0.10), 0 1px 3px rgba(15,23,42,0.04);
  border-left: 4px solid var(--teal);
}
.rec-card .rank {
  display: inline-block;
  background: var(--teal);
  color: white;
  width: 28px; height: 28px;
  border-radius: 50%;
  font-weight: 700;
  text-align: center;
  line-height: 28px;
  margin-right: 10px;
  font-size: 0.85rem;
}
.rec-card .brand-sku { font-size: 1.05rem; font-weight: 600; color: var(--ink); }
.rec-card .type-line { font-size: 0.85rem; color: var(--muted); margin-top: 2px; }
.rec-card .specs {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  margin-top: 14px;
  font-size: 0.88rem;
}
.rec-card .spec-label { color: var(--muted); font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.04em; }
.rec-card .spec-value { color: var(--ink); font-weight: 600; margin-top: 2px; }
.rec-card .score-pill {
  float: right;
  background: var(--teal-light);
  color: var(--teal-dark);
  font-weight: 700;
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 0.85rem;
}
.flag-pill {
  display: inline-block;
  background: var(--amber-bg);
  color: var(--amber-ink);
  border: 1px solid var(--amber-border);
  border-radius: 6px;
  padding: 2px 8px;
  font-size: 0.75rem;
  margin: 6px 6px 0 0;
}
.vec-panel {
  background: #f1f5f9;
  border-radius: 10px;
  padding: 14px 18px;
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
  font-size: 0.82rem;
  color: var(--ink);
}
hr { border: none; border-top: 1px solid #e2e8f0; margin: 24px 0; }
</style>
"""

st.markdown(CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Option dictionaries (display label ↔ internal id)
# ---------------------------------------------------------------------------

JOB_OPTIONS = [
    ("lift_and_store", "Lift and store"),
    ("lift_and_pressurise_directly", "Lift and pressurise directly"),
    ("boost_pressure", "Boost pressure from existing storage or supply"),
    ("drain_water", "Drain or remove water"),
    ("pump_sewage", "Pump out sewage or dirty water"),
]
SOURCE_OPTIONS = [
    ("borewell", "Borewell"),
    ("open_well", "Open well or pond"),
    ("underground_sump", "Underground sump or storage tank"),
    ("overhead_tank", "Overhead tank"),
    ("municipal", "Municipal line / direct supply"),
    ("sewage_pit", "Sewage or drainage pit"),
    ("open_ground", "Open ground water (canal, river, farm channel)"),
]
LIFT_OPTIONS = [
    ("ground", "Same level / No lift / Ground floor only"),
    ("floor_1", "1st floor (~3 m)"),
    ("floor_2", "2nd floor (~6 m)"),
    ("floor_3", "3rd floor (~9 m)"),
    ("floor_4", "4th floor (~12 m)"),
    ("floors_5_10", "5–10 floors (~15–30 m)"),
    ("floors_11_15", "11–15 floors (~33–45 m)"),
    ("floors_16_25", "16–25 floors (~48–75 m)"),
    ("floors_26_40", "26–40 floors (~78–120 m)"),
    ("floors_41_60", "41–60 floors (~123–180 m)"),
    ("floors_above_60", "Above 60 floors (above ~180 m)"),
]
DEMAND_OPTIONS = [
    ("very_small", "Very small (up to ~1,000 L/day)"),
    ("small", "Small (~1,000–3,000 L/day)"),
    ("medium", "Medium (~3,000–10,000 L/day)"),
    ("large", "Large (~10,000–50,000 L/day)"),
    ("very_large", "Very large (~50,000–200,000 L/day)"),
    ("bulk", "Bulk (above ~200,000 L/day)"),
]
SETTING_OPTIONS = [
    ("home", "Home"),
    ("farm", "Farm / agriculture"),
    ("shop_small_comm", "Shop / office / small commercial"),
    ("large_commercial", "Large commercial or institutional"),
    ("light_industry", "Light industry / warehouse / construction site"),
]
DEST_OPTIONS = [
    ("overhead_tank", "Overhead tank"),
    ("ground_sump", "Ground-level storage tank or sump"),
    ("direct_pipes", "Direct to building pipes (no tank)"),
    ("irrigation", "Irrigation lines / open field / livestock"),
    ("industrial_process", "Industrial process or treatment system"),
    ("tanker", "Tanker or external transfer point"),
]
C1_OPTIONS = [
    ("casing_4in", "4 inch (100 mm)"),
    ("casing_6in", "6 inch (150 mm)"),
    ("casing_8in", "8 inch (200 mm)"),
    ("casing_10in", "10 inch (250 mm)"),
    ("casing_12in_plus", "12 inch (300 mm) and above"),
]
C2_OPTIONS = [
    ("under_50ft", "Under 50 ft (under 15 m)"),
    ("50_100ft", "50–100 ft (15–30 m)"),
    ("100_200ft", "100–200 ft (30–60 m)"),
    ("200_300ft", "200–300 ft (60–90 m)"),
    ("300_450ft", "300–450 ft (90–135 m)"),
    ("450_600ft", "450–600 ft (135–180 m)"),
    ("600_800ft", "600–800 ft (180–245 m)"),
    ("800_1000ft", "800–1,000 ft (245–305 m)"),
    ("above_1000ft", "Above 1,000 ft (above 305 m)"),
]
C3_OPTIONS = [
    ("shallow_under_30ft", "Shallow open well (under 30 ft)"),
    ("medium_30_60ft", "Medium (30–60 ft)"),
    ("deep_above_60ft", "Deep open well (above 60 ft)"),
]
C4_OPTIONS = [
    ("1_4", "1–4 outlets", 2),
    ("5_12", "5–12 outlets", 8),
    ("13_20", "13–20 outlets", 16),
    ("21_35", "21–35 outlets", 28),
    ("36_75", "36–75 outlets", 55),
    ("76_150", "76–150 outlets", 113),
    ("above_150", "More than 150 outlets", 200),
]
C5_OPTIONS = [
    ("light", "Light (most outlets used one at a time)"),
    ("moderate", "Moderate (half the outlets typically running together)"),
    ("heavy", "Heavy (many outlets running together)"),
    ("constant_peak", "Constant peak (full simultaneous demand)"),
]
C6_OPTIONS = [
    ("clean_water", "Clean water"),
    ("lightly_soiled", "Lightly soiled (grey water)"),
    ("solids_waste", "Solids and waste"),
    ("heavy_sewage", "Heavy sewage"),
    ("industrial_effluent", "Industrial effluent (out of scope)"),
]
C7_OPTIONS = [("Single", "Single-phase"), ("Three", "Three-phase")]
C8_OPTIONS = [
    ("moderate", "Moderate (2–6 hours/day)"),
    ("heavy", "Heavy (6–12 hours/day)"),
    ("continuous", "Continuous (12+ hours/day)"),
]
C9_OPTIONS = [
    ("very_low", "Very low voltage (below 180 V)"),
    ("low", "Low voltage (180–200 V)"),
    ("normal", "Normal voltage (200–240 V)"),
]


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def picker(label: str, field: str, options, ans: dict, help_text: str = ""):
    """
    Radio-like single-select that disables options invalidated by current
    answers, with the disabling reason shown inline.
    """
    st.markdown(f'<div class="section-title">{label}</div>', unsafe_allow_html=True)
    if help_text:
        st.markdown(f'<div class="section-help">{help_text}</div>', unsafe_allow_html=True)

    labels, ids, disabled_reasons = [], [], {}
    for opt in options:
        oid, olabel = opt[0], opt[1]
        ids.append(oid)
        disabled, reason = is_disabled(field, oid, ans)
        if disabled:
            labels.append(f"~~{olabel}~~  (unavailable)")
            disabled_reasons[olabel] = reason
        else:
            labels.append(olabel)

    current = ans.get(field)
    default_idx = ids.index(current) if current in ids else 0
    chosen_label = st.radio(
        label, labels, index=default_idx, key=f"radio_{field}",
        label_visibility="collapsed",
    )
    chosen_idx = labels.index(chosen_label)
    chosen_id = ids[chosen_idx]

    # If user chose a disabled option, surface why and don't accept it
    if "(unavailable)" in chosen_label:
        original_label = options[chosen_idx][1]
        st.markdown(
            f'<div class="error-box">⚠ This option is unavailable: '
            f'{disabled_reasons.get(original_label, "")}</div>',
            unsafe_allow_html=True,
        )
        return None  # signal: invalid

    # Show extra payload (e.g. outlet count) if the option has one
    return chosen_id if len(options[chosen_idx]) <= 2 else (chosen_id, options[chosen_idx][2])


def show_soft_warnings(ans: dict):
    """Render any soft-warning rules that fire (e.g. Rule 59)."""
    for rid, sev, reason in evaluate(ans):
        if sev == "soft":
            st.markdown(
                f'<div class="warning-box">ℹ <b>Note ({rid}):</b> {reason}</div>',
                unsafe_allow_html=True,
            )


def render_card(rank: int, row: pd.Series, lift_flag_list):
    """Render one recommendation card."""
    flags = list(row.get("flags") or [])
    flags += [f[0] for f in lift_flag_list]

    flag_pills = "".join(
        f'<span class="flag-pill">{f.replace("_", " ")}</span>' for f in flags
    )

    head_str = f"{row['Min Head (m)']:.0f}–{row['Max Head (m)']:.0f} m"
    flow_str = f"{row['Min Flow (LPH)']:.0f}–{row['Max Flow (LPH)']:.0f} LPH"
    phase = row["Phase"] if pd.notna(row["Phase"]) and row["Phase"] != "Not Found" else "Unknown"

    html = f"""
    <div class="rec-card">
      <span class="score-pill">Score {int(row['score'])}</span>
      <span class="rank">{rank}</span>
      <span class="brand-sku">{row['Brand']} — {row['SKU']}</span>
      <div class="type-line">{row['Type']}</div>
      <div class="specs">
        <div><div class="spec-label">HP</div><div class="spec-value">{row['HP']}</div></div>
        <div><div class="spec-label">Head</div><div class="spec-value">{head_str}</div></div>
        <div><div class="spec-label">Flow</div><div class="spec-value">{flow_str}</div></div>
        <div><div class="spec-label">Phase</div><div class="spec-value">{phase}</div></div>
      </div>
      {f'<div style="margin-top:12px">{flag_pills}</div>' if flag_pills else ''}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------

def main():
    st.markdown(
        '<div class="hero">'
        '<h1>💧 Pump Selection Assistant</h1>'
        '<p>Answer a few questions and we will recommend the best-matching pumps from a 4,020-SKU catalogue.</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    ans = {}

    # ----- Core factors -----------------------------------------------------
    st.markdown('<div class="step-badge">STEP 1 OF 5 · JOB</div>', unsafe_allow_html=True)
    ans["job"] = picker("What is the pump supposed to do?", "job", JOB_OPTIONS, ans,
                         "Pick the job that best describes what you need the pump for.")
    if ans["job"] is None: return

    st.markdown('<hr/>', unsafe_allow_html=True)
    st.markdown('<div class="step-badge">STEP 2 OF 5 · SOURCE</div>', unsafe_allow_html=True)
    ans["source"] = picker("Where is the water coming from?", "source", SOURCE_OPTIONS, ans)
    if ans["source"] is None: return

    st.markdown('<hr/>', unsafe_allow_html=True)
    st.markdown('<div class="step-badge">STEP 3 OF 5 · LIFT</div>', unsafe_allow_html=True)
    ans["lift"] = picker("How high does the water need to go?", "lift", LIFT_OPTIONS, ans)
    if ans["lift"] is None: return

    st.markdown('<hr/>', unsafe_allow_html=True)
    st.markdown('<div class="step-badge">STEP 4 OF 5 · DEMAND</div>', unsafe_allow_html=True)
    ans["demand"] = picker("How much water is needed?", "demand", DEMAND_OPTIONS, ans)
    if ans["demand"] is None: return

    st.markdown('<hr/>', unsafe_allow_html=True)
    st.markdown('<div class="step-badge">STEP 5 OF 5 · SETTING</div>', unsafe_allow_html=True)
    ans["setting"] = picker("What kind of place is it?", "setting", SETTING_OPTIONS, ans)
    if ans["setting"] is None: return

    # ----- Conditional factors ---------------------------------------------
    st.markdown('<hr/>', unsafe_allow_html=True)
    st.markdown('## Additional details')

    # C0 — Destination (Lift jobs only)
    if ans["job"] in {"lift_and_store", "lift_and_pressurise_directly"}:
        ans["c0_destination"] = picker("Where does the water end up?", "c0_destination",
                                        DEST_OPTIONS, ans)
        if ans["c0_destination"] is None: return

    # C1 + C2 — Borewell casing & depth
    if ans["source"] == "borewell":
        ans["c1_casing"] = picker("Borewell casing diameter", "c1_casing", C1_OPTIONS, ans)
        if ans["c1_casing"] is None: return
        ans["c2_depth"] = picker("Borewell water depth (static rest level)", "c2_depth",
                                  C2_OPTIONS, ans,
                                  "The depth from ground to the top of the water column when the pump is off "
                                  "— not the total drilled depth of the borewell.")
        if ans["c2_depth"] is None: return

    # C3 — Open well depth
    if ans["source"] == "open_well":
        ans["c3_well_depth"] = picker("Open well water depth", "c3_well_depth", C3_OPTIONS, ans)
        if ans["c3_well_depth"] is None: return

    # C4 + C5 — Outlets & usage (pressure jobs)
    pressure_jobs = {"boost_pressure", "lift_and_pressurise_directly"}
    if ans["job"] in pressure_jobs:
        c4_result = picker("Number of outlets", "c4_outlets", C4_OPTIONS, ans)
        if c4_result is None: return
        if isinstance(c4_result, tuple):
            ans["c4_outlets"], ans["c4_outlets_count"] = c4_result
        else:
            ans["c4_outlets"] = c4_result

        ans["c5_usage"] = picker("How simultaneously are outlets used?", "c5_usage",
                                  C5_OPTIONS, ans)
        if ans["c5_usage"] is None: return

    # C6 — Water quality (drainage & sewage)
    if ans["job"] in {"drain_water", "pump_sewage"}:
        ans["c6_quality"] = picker("Water quality / contents", "c6_quality", C6_OPTIONS, ans)
        if ans["c6_quality"] is None: return
        if ans["c6_quality"] == "industrial_effluent":
            st.markdown(
                '<div class="error-box">⚠ <b>Specialised pump required.</b> '
                'Industrial effluent is outside the scope of this catalogue. '
                'Please consult a specialist.</div>',
                unsafe_allow_html=True,
            )
            return

    # C7 — Phase (always available; defaults from Setting)
    needs_phase_confirm = (
        (ans["setting"] == "home" and (
            (ans["lift"] in {"floors_5_10", "floors_11_15", "floors_16_25",
                              "floors_26_40", "floors_41_60", "floors_above_60"}) or
            (ans["demand"] in {"large", "very_large", "bulk"}) or
            (ans.get("c2_depth") in {"300_450ft", "450_600ft", "600_800ft",
                                       "800_1000ft", "above_1000ft"})
        )) or
        (ans["setting"] == "shop_small_comm")
    )
    from vector import SETTING_DEFAULTS
    default_phase, _ = SETTING_DEFAULTS[ans["setting"]]
    if needs_phase_confirm:
        ans["c7_phase"] = picker(
            f"Power supply phase (default for this setting: {default_phase}-phase)",
            "c7_phase", C7_OPTIONS, ans,
            "Please confirm or override the default — small commercial connections vary.",
        )
        if ans["c7_phase"] is None: return
    else:
        ans["c7_phase"] = default_phase

    # C8 — Duty cycle (triggered by industrial-scale settings or Large+ demand)
    c8_triggered = ans["setting"] in {"farm", "light_industry", "large_commercial"} \
                   or ans["demand"] in {"large", "very_large", "bulk"}
    if c8_triggered:
        ans["c8_duty"] = picker("Duty cycle (hours per day)", "c8_duty", C8_OPTIONS, ans)
        if ans["c8_duty"] is None: return

    # C9 — Voltage (single-phase only)
    if ans["c7_phase"] == "Single":
        ans["c9_voltage"] = picker(
            "Lowest voltage at pump site",
            "c9_voltage", C9_OPTIONS, ans,
            "What is the lowest voltage you usually get at the pump site?",
        )
        if ans["c9_voltage"] is None: return

    # ----- Soft warnings (Rule 59 etc.) -------------------------------------
    show_soft_warnings(ans)

    # ----- Build requirement vector ----------------------------------------
    vec = build_vector(ans)

    st.markdown('<hr/>', unsafe_allow_html=True)
    with st.expander("Show calculation details (requirement vector)"):
        st.markdown('<div class="vec-panel">', unsafe_allow_html=True)
        st.markdown(
            f"**allowed_pump_types** = {vec['allowed_pump_types']}  \n"
            f"**required_min_head**  = {vec['required_min_head']} m  \n"
            f"**typical_head**       = {vec['typical_head']} m  \n"
            f"**required_min_flow**  = {vec['required_min_flow']:.0f} LPH  \n"
            f"**typical_flow**       = {vec['typical_flow']:.0f} LPH  \n"
            f"**allowed_phase**      = {sorted(vec['allowed_phase'])}  \n"
            f"**final_phase**        = {vec['final_phase']}  \n"
            f"**hp_cap (preferred)** = {vec['hp_cap']}  \n"
            f"**special**            = {vec['special']}"
        )
        st.markdown('</div>', unsafe_allow_html=True)

    # ----- Filter + score --------------------------------------------------
    df = get_catalogue()
    survivors, trace = filter_skus(df, vec)
    scored = score_skus(survivors, vec)

    with st.expander("Show filter trace (step-by-step row counts)"):
        for t in trace:
            st.text(f"  Step {t['step']:>3} : {t['label']:<60} → {t['rows_left']:>5} rows")

    # ----- Lift flags (informational) --------------------------------------
    l_flags = lift_flags(ans)
    for code, msg in l_flags:
        st.markdown(f'<div class="warning-box">ℹ <b>{code}:</b> {msg}</div>',
                    unsafe_allow_html=True)

    # ----- Results ---------------------------------------------------------
    st.markdown('<hr/>', unsafe_allow_html=True)
    st.markdown(f"## Top recommendations  ·  {len(scored)} candidate SKUs found")

    if len(scored) == 0:
        st.markdown(
            '<div class="error-box">No SKUs match these requirements. '
            'This may indicate a very specialised or out-of-scope use case. '
            'Please consult a pump specialist.</div>',
            unsafe_allow_html=True,
        )
        return

    top5 = scored.head(5)
    for rank, (_, row) in enumerate(top5.iterrows(), start=1):
        render_card(rank, row, l_flags)


if __name__ == "__main__":
    main()
