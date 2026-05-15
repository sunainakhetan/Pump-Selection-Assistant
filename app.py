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
from vector import build_vector, SETTING_DEFAULTS

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
  --bg: #f6f8fb;
  --card: #ffffff;
  --ink: #0f172a;
  --muted: #64748b;
  --line: #e2e8f0;
  --cyan: #0891b2;
  --cyan-dark: #0e7490;
  --cyan-soft: #ecfeff;
  --cyan-pill: #cffafe;
  --shadow: 0 12px 32px rgba(15, 23, 42, 0.08);
  --amber-bg: #fffbeb;
  --amber-border: #fde68a;
  --amber-ink: #92400e;
  --red-bg: #fef2f2;
  --red-border: #fecaca;
  --red-ink: #991b1b;
}

html, body, [class*="css"] {
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
    "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}

body, .stApp {
  background: var(--bg);
  color: var(--ink);
}

.block-container {
  padding-top: 0 !important;
  padding-bottom: 4rem;
  max-width: 1280px;
}

#MainMenu, footer, header {
  visibility: hidden;
}

h1, h2, h3 {
  color: var(--ink);
  letter-spacing: -0.035em;
}

.hero-shell {
  margin: 0 calc(50% - 50vw) 26px;
  padding: 42px max(24px, calc(50vw - 640px)) 38px;
  background: linear-gradient(135deg, #ffffff 0%, #ecfeff 100%);
  border-bottom: 1px solid var(--line);
}

.hero-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: 28px;
  align-items: center;
}

.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: var(--cyan-pill);
  color: var(--cyan-dark);
  border-radius: 999px;
  padding: 8px 13px;
  font-size: 0.86rem;
  font-weight: 800;
}

.hero-title {
  max-width: 780px;
  margin: 14px 0 14px;
  font-size: clamp(2.1rem, 5vw, 3.65rem);
  line-height: 1.02;
  font-weight: 900;
  letter-spacing: -0.06em;
}

.hero-copy {
  max-width: 780px;
  color: var(--muted);
  line-height: 1.55;
  font-size: 1.04rem;
  margin: 0;
}

.status-card {
  background: rgba(255,255,255,0.78);
  border: 1px solid var(--line);
  border-radius: 24px;
  padding: 18px;
  box-shadow: var(--shadow);
}

.status-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-weight: 900;
}

.progress-rail {
  height: 10px;
  background: #e2e8f0;
  border-radius: 999px;
  overflow: hidden;
  margin: 12px 0 14px;
}

.progress-fill {
  display: block;
  height: 100%;
  background: var(--cyan);
  border-radius: 999px;
}

.pill-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.ui-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border-radius: 999px;
  background: #f1f5f9;
  color: #475569;
  padding: 6px 10px;
  font-size: 0.76rem;
  font-weight: 800;
}

.question-panel,
.side-panel {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 28px;
  box-shadow: var(--shadow);
  padding: 20px;
  margin-bottom: 18px;
}

.side-stack {
  position: sticky;
  top: 18px;
}

.step-badge {
  display: inline-block;
  color: var(--cyan);
  font-size: 0.78rem;
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: 0.09em;
  margin-bottom: 6px;
}

.section-title {
  font-size: 1.38rem;
  font-weight: 900;
  color: var(--ink);
  margin: 0 0 6px;
  line-height: 1.18;
}

.section-help {
  font-size: 0.92rem;
  color: var(--muted);
  margin: 0 0 14px;
  line-height: 1.45;
}

div[data-testid="stRadio"] > label {
  display: none;
}

div[data-testid="stRadio"] div[role="radiogroup"] {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

div[data-testid="stRadio"] label {
  min-height: 76px;
  align-items: flex-start !important;
  border: 1px solid var(--line);
  background: #fff;
  border-radius: 18px;
  padding: 14px 15px;
  transition: 0.18s ease;
}

div[data-testid="stRadio"] label:hover {
  border-color: #67e8f9;
  background: #f8fafc;
  transform: translateY(-1px);
}

div[data-testid="stRadio"] label:has(input:checked) {
  border-color: var(--cyan);
  background: var(--cyan-soft);
  box-shadow: 0 0 0 3px rgba(8, 145, 178, 0.12);
}

div[data-testid="stRadio"] label p {
  font-weight: 800;
  color: #1e293b;
  line-height: 1.25;
}

.warning-box,
.error-box,
.info-box {
  border-radius: 16px;
  padding: 12px 13px;
  margin: 12px 0;
  font-size: 0.9rem;
  line-height: 1.42;
  border: 1px solid;
}

.warning-box {
  background: var(--amber-bg);
  border-color: var(--amber-border);
  color: var(--amber-ink);
}

.error-box {
  background: var(--red-bg);
  border-color: var(--red-border);
  color: var(--red-ink);
}

.info-box {
  background: var(--cyan-soft);
  border-color: #a5f3fc;
  color: #155e75;
}

.side-title-row {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: start;
}

.side-title {
  margin: 0;
  font-size: 1.45rem;
  line-height: 1.15;
  font-weight: 900;
}

.side-subtitle {
  margin: 6px 0 0;
  color: var(--muted);
  line-height: 1.45;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 16px;
}

.metric-card {
  background: #f8fafc;
  border: 1px solid #edf2f7;
  border-radius: 16px;
  padding: 12px;
  min-height: 84px;
}

.metric-card small {
  display: block;
  color: var(--muted);
  font-size: 0.68rem;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  font-weight: 900;
}

.metric-card strong {
  display: block;
  margin-top: 5px;
  color: var(--ink);
  font-size: 1.08rem;
  line-height: 1.15;
}

.metric-card span {
  display: block;
  margin-top: 5px;
  color: var(--muted);
  font-size: 0.76rem;
  line-height: 1.3;
}

.vec-panel {
  background: #0f172a;
  color: #e2e8f0;
  border-radius: 18px;
  padding: 14px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.78rem;
  overflow: auto;
}

.stTextInput input {
  border-radius: 15px !important;
  border: 1px solid var(--line) !important;
  padding: 12px 14px !important;
  box-shadow: none !important;
}

.rec-card {
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 14px;
  margin-top: 12px;
  box-shadow: none;
}

.rec-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.rec-card .score-pill {
  background: #0f172a;
  color: #fff;
  border-radius: 13px;
  padding: 7px 10px;
  font-weight: 900;
  font-size: 0.82rem;
  white-space: nowrap;
}

.rec-card .brand-sku {
  font-size: 1.05rem;
  font-weight: 900;
  line-height: 1.25;
  color: var(--ink);
}

.rec-card .type-line {
  font-size: 0.82rem;
  color: var(--muted);
  margin-top: 3px;
}

.rec-card .rank {
  color: var(--cyan-dark);
  font-weight: 900;
  margin-right: 6px;
}

.rec-card .specs {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-top: 12px;
}

.rec-card .spec-box {
  background: #f8fafc;
  border-radius: 12px;
  padding: 9px;
}

.rec-card .spec-label {
  color: var(--muted);
  font-size: 0.64rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-weight: 900;
}

.rec-card .spec-value {
  color: var(--ink);
  font-weight: 850;
  margin-top: 3px;
  font-size: 0.82rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.flag-pill {
  display: inline-block;
  background: var(--amber-bg);
  color: var(--amber-ink);
  border: 1px solid var(--amber-border);
  border-radius: 999px;
  padding: 4px 8px;
  font-size: 0.72rem;
  font-weight: 800;
  margin: 8px 6px 0 0;
}

.empty-card {
  border: 1px dashed #cbd5e1;
  border-radius: 18px;
  background: #f8fafc;
  text-align: center;
  padding: 22px;
  color: var(--muted);
  margin-top: 14px;
}

@media (max-width: 980px) {
  .hero-grid {
    grid-template-columns: 1fr;
  }

  .side-stack {
    position: static;
  }
}

@media (max-width: 620px) {
  .hero-shell {
    padding: 28px 16px;
  }

  div[data-testid="stRadio"] div[role="radiogroup"],
  .metric-grid,
  .rec-card .specs {
    grid-template-columns: 1fr;
  }

  .question-panel,
  .side-panel {
    border-radius: 22px;
    padding: 16px;
  }
}
</style>
"""

st.markdown(CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Option dictionaries
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

C7_OPTIONS = [
    ("Single", "Single-phase"),
    ("Three", "Three-phase"),
]

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

def reset_app():
    for key in list(st.session_state.keys()):
        if key.startswith("radio_") or key in {"rec_search"}:
            del st.session_state[key]


def option_label(option):
    return option[1]


def render_question(step: str, title: str, field: str, options, ans: dict, help_text: str = ""):
    st.markdown('<div class="question-panel">', unsafe_allow_html=True)
    st.markdown(f'<div class="step-badge">{step}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)

    if help_text:
        st.markdown(f'<div class="section-help">{help_text}</div>', unsafe_allow_html=True)

    display_options = []
    option_by_label = {}
    disabled_reasons = {}

    for opt in options:
        oid, label = opt[0], opt[1]
        disabled, reason = is_disabled(field, oid, ans)
        display = f"Unavailable · {label}" if disabled else label
        display_options.append(display)
        option_by_label[display] = opt
        if disabled:
            disabled_reasons[display] = reason

    key = f"radio_{field}"
    chosen_label = st.radio(
        title,
        display_options,
        key=key,
        index=None,
        label_visibility="collapsed",
    )

    if not chosen_label:
        st.markdown('</div>', unsafe_allow_html=True)
        return None

    if chosen_label.startswith("Unavailable ·"):
        st.markdown(
            f'<div class="error-box">⚠ This option is unavailable: '
            f'{disabled_reasons.get(chosen_label, "")}</div>',
            unsafe_allow_html=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)
        return None

    chosen = option_by_label[chosen_label]
    st.markdown('</div>', unsafe_allow_html=True)

    if len(chosen) > 2:
        return chosen[0], chosen[2]
    return chosen[0]


def show_soft_warnings(ans: dict):
    for rid, sev, reason in evaluate(ans):
        if sev == "soft":
            st.markdown(
                f'<div class="warning-box">ℹ <b>Note ({rid}):</b> {reason}</div>',
                unsafe_allow_html=True,
            )


def vector_metric(label: str, value, hint: str = ""):
    st.markdown(
        f"""
        <div class="metric-card">
          <small>{label}</small>
          <strong>{value}</strong>
          {f'<span>{hint}</span>' if hint else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_vector_panel(vec: dict | None):
    st.markdown('<div class="side-panel">', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="side-title-row">
          <div>
            <div class="side-title">Requirement vector</div>
            <div class="side-subtitle">Calculated from the selected answers.</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if vec is None:
        st.markdown('<div class="metric-grid">', unsafe_allow_html=True)
        vector_metric("Pump types", "—", "Answer job/source")
        vector_metric("Min head", "—", "Answer lift")
        vector_metric("Min flow", "—", "Answer demand")
        vector_metric("Phase", "—", "Auto-filled from setting unless confirmation is needed")
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        pump_types = ", ".join(vec["allowed_pump_types"]) if vec["allowed_pump_types"] else "None"
        st.markdown('<div class="metric-grid">', unsafe_allow_html=True)
        vector_metric("Pump types", pump_types)
        vector_metric("Min head", f"{vec['required_min_head']} m", f"Typical: {vec['typical_head']} m")
        vector_metric("Min flow", f"{vec['required_min_flow']:.0f} LPH", f"Typical: {vec['typical_flow']:.0f} LPH")
        vector_metric("Phase", vec["final_phase"], f"Allowed: {', '.join(sorted(vec['allowed_phase']))}")
        st.markdown('</div>', unsafe_allow_html=True)

        with st.expander("Show full vector"):
            st.markdown(
                f"""
                <div class="vec-panel">
                allowed_pump_types = {vec['allowed_pump_types']}<br>
                required_min_head = {vec['required_min_head']} m<br>
                typical_head = {vec['typical_head']} m<br>
                required_min_flow = {vec['required_min_flow']:.0f} LPH<br>
                typical_flow = {vec['typical_flow']:.0f} LPH<br>
                allowed_phase = {sorted(vec['allowed_phase'])}<br>
                final_phase = {vec['final_phase']}<br>
                hp_cap = {vec['hp_cap']}<br>
                special = {vec['special']}
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown('</div>', unsafe_allow_html=True)


def render_card(rank: int, row: pd.Series, lift_flag_list):
    flags = list(row.get("flags") or [])
    flags += [f[0] for f in lift_flag_list]

    flag_pills = "".join(
        f'<span class="flag-pill">{flag.replace("_", " ")}</span>' for flag in flags
    )

    head_str = f"{row['Min Head (m)']:.0f}–{row['Max Head (m)']:.0f} m"
    flow_str = f"{row['Min Flow (LPH)']:.0f}–{row['Max Flow (LPH)']:.0f} LPH"
    phase = row["Phase"] if pd.notna(row["Phase"]) and row["Phase"] != "Not Found" else "Unknown"

    st.markdown(
        f"""
        <div class="rec-card">
          <div class="rec-top">
            <div>
              <div class="brand-sku"><span class="rank">#{rank}</span>{row['Brand']} — {row['SKU']}</div>
              <div class="type-line">{row['Type']}</div>
            </div>
            <div class="score-pill">Score {int(row['score'])}</div>
          </div>
          <div class="specs">
            <div class="spec-box">
              <div class="spec-label">HP</div>
              <div class="spec-value">{row['HP']}</div>
            </div>
            <div class="spec-box">
              <div class="spec-label">Head</div>
              <div class="spec-value">{head_str}</div>
            </div>
            <div class="spec-box">
              <div class="spec-label">Flow</div>
              <div class="spec-value">{flow_str}</div>
            </div>
            <div class="spec-box">
              <div class="spec-label">Phase</div>
              <div class="spec-value">{phase}</div>
            </div>
          </div>
          {f'<div>{flag_pills}</div>' if flag_pills else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_recommendations(scored: pd.DataFrame | None, lift_flag_list):
    st.markdown('<div class="side-panel">', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="side-title">Recommendations</div>
        <div class="side-subtitle">Top ranked matching SKUs from the Excel catalogue.</div>
        """,
        unsafe_allow_html=True,
    )

    query = st.text_input(
        "Filter recommendations",
        placeholder="Filter by SKU, brand, or type",
        key="rec_search",
        label_visibility="collapsed",
    )

    if scored is None:
        st.markdown(
            '<div class="empty-card"><b>Answer the required questions.</b><br>'
            'Recommendations will appear once the requirement vector is complete.</div>',
            unsafe_allow_html=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)
        return

    if len(scored) == 0:
        st.markdown(
            '<div class="empty-card"><b>No matching SKUs found.</b><br>'
            'This may be a specialised or out-of-scope use case. Please consult a pump specialist.</div>',
            unsafe_allow_html=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)
        return

    view = scored.copy()
    if query:
        q = query.strip().lower()
        mask = (
            view["SKU"].astype(str).str.lower().str.contains(q, na=False)
            | view["Brand"].astype(str).str.lower().str.contains(q, na=False)
            | view["Type"].astype(str).str.lower().str.contains(q, na=False)
        )
        view = view[mask]

    st.markdown(
        f'<div class="info-box"><b>{len(scored)}</b> candidate SKUs found. Showing top matches.</div>',
        unsafe_allow_html=True,
    )

    for rank, (_, row) in enumerate(view.head(5).iterrows(), start=1):
        render_card(rank, row, lift_flag_list)

    if len(view) == 0:
        st.markdown(
            '<div class="empty-card">No recommendations match this search.</div>',
            unsafe_allow_html=True,
        )

    st.markdown('</div>', unsafe_allow_html=True)


def required_answer_count(ans: dict):
    required = ["job", "source", "lift", "demand", "setting"]

    if ans.get("job") in {"lift_and_store", "lift_and_pressurise_directly"}:
        required.append("c0_destination")

    if ans.get("source") == "borewell":
        required += ["c1_casing", "c2_depth"]

    if ans.get("source") == "open_well":
        required.append("c3_well_depth")

    if ans.get("job") in {"boost_pressure", "lift_and_pressurise_directly"}:
        required += ["c4_outlets", "c5_usage"]

    if ans.get("job") in {"drain_water", "pump_sewage"}:
        required.append("c6_quality")

    if ans.get("setting") and ans.get("lift") and ans.get("demand"):
        needs_phase_confirm = (
            (ans["setting"] == "home" and (
                ans["lift"] in {
                    "floors_5_10", "floors_11_15", "floors_16_25",
                    "floors_26_40", "floors_41_60", "floors_above_60",
                }
                or ans["demand"] in {"large", "very_large", "bulk"}
                or ans.get("c2_depth") in {
                    "300_450ft", "450_600ft", "600_800ft",
                    "800_1000ft", "above_1000ft",
                }
            ))
            or ans["setting"] == "shop_small_comm"
        )
        if needs_phase_confirm:
            required.append("c7_phase")

    if ans.get("setting") in {"farm", "light_industry", "large_commercial"} or ans.get("demand") in {"large", "very_large", "bulk"}:
        required.append("c8_duty")

    if ans.get("c7_phase") == "Single":
        required.append("c9_voltage")

    answered = sum(1 for key in required if ans.get(key) is not None)
    return answered, len(required)


def render_hero(progress_pct: int, sku_count: int):
    st.markdown(
        f"""
        <div class="hero-shell">
          <div class="hero-grid">
            <div>
              <div class="hero-badge">💧 Pump-selection assistant</div>
              <div class="hero-title">Choose a pump from the current catalogue.</div>
              <p class="hero-copy">
                Answer a few questions and get the best-matching pumps from the current SKU catalogue.
                Invalid combinations are called out immediately using the built-in rules.
              </p>
            </div>
            <div class="status-card">
              <div class="status-row">
                <span>Progress</span>
                <span>{progress_pct}%</span>
              </div>
              <div class="progress-rail">
                <span class="progress-fill" style="width:{progress_pct}%"></span>
              </div>
              <div class="pill-row">
                <span class="ui-pill">{sku_count:,} SKUs loaded</span>
                <span class="ui-pill">Catalogue based</span>
              </div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------

def main():
    try:
        sku_count = len(get_catalogue())
    except Exception:
        sku_count = 0

    hero_slot = st.empty()

    left, right = st.columns([1.85, 1], gap="large")

    ans = {}

    with left:
        ans["job"] = render_question(
            "Step 1 of 5 · Job",
            "What is the pump supposed to do?",
            "job",
            JOB_OPTIONS,
            ans,
            "Pick the job that best describes what you need the pump for.",
        )

        ans["source"] = render_question(
            "Step 2 of 5 · Source",
            "Where is the water coming from?",
            "source",
            SOURCE_OPTIONS,
            ans,
        )

        ans["lift"] = render_question(
            "Step 3 of 5 · Lift",
            "How high does the water need to go?",
            "lift",
            LIFT_OPTIONS,
            ans,
        )

        ans["demand"] = render_question(
            "Step 4 of 5 · Demand",
            "How much water is needed?",
            "demand",
            DEMAND_OPTIONS,
            ans,
        )

        ans["setting"] = render_question(
            "Step 5 of 5 · Setting",
            "What kind of place is it?",
            "setting",
            SETTING_OPTIONS,
            ans,
        )

        if ans.get("job") in {"lift_and_store", "lift_and_pressurise_directly"}:
            ans["c0_destination"] = render_question(
                "Additional detail",
                "Where does the water end up?",
                "c0_destination",
                DEST_OPTIONS,
                ans,
            )

        if ans.get("source") == "borewell":
            ans["c1_casing"] = render_question(
                "Additional detail",
                "Borewell casing diameter",
                "c1_casing",
                C1_OPTIONS,
                ans,
            )

            ans["c2_depth"] = render_question(
                "Additional detail",
                "Borewell water depth (static rest level)",
                "c2_depth",
                C2_OPTIONS,
                ans,
                "The depth from ground to the top of the water column when the pump is off — not the total drilled depth.",
            )

        if ans.get("source") == "open_well":
            ans["c3_well_depth"] = render_question(
                "Additional detail",
                "Open well water depth",
                "c3_well_depth",
                C3_OPTIONS,
                ans,
            )

        if ans.get("job") in {"boost_pressure", "lift_and_pressurise_directly"}:
            c4_result = render_question(
                "Additional detail",
                "Number of outlets",
                "c4_outlets",
                C4_OPTIONS,
                ans,
            )

            if isinstance(c4_result, tuple):
                ans["c4_outlets"], ans["c4_outlets_count"] = c4_result
            else:
                ans["c4_outlets"] = c4_result

            ans["c5_usage"] = render_question(
                "Additional detail",
                "How simultaneously are outlets used?",
                "c5_usage",
                C5_OPTIONS,
                ans,
            )

        if ans.get("job") in {"drain_water", "pump_sewage"}:
            ans["c6_quality"] = render_question(
                "Additional detail",
                "Water quality / contents",
                "c6_quality",
                C6_OPTIONS,
                ans,
            )

            if ans.get("c6_quality") == "industrial_effluent":
                st.markdown(
                    '<div class="error-box">⚠ <b>Specialised pump required.</b> '
                    'Industrial effluent is outside the scope of this catalogue. '
                    'Please consult a specialist.</div>',
                    unsafe_allow_html=True,
                )

        if ans.get("setting"):
            default_phase, _ = SETTING_DEFAULTS[ans["setting"]]
        else:
            default_phase = None

        needs_phase_confirm = False
        if ans.get("setting") and ans.get("lift") and ans.get("demand"):
            needs_phase_confirm = (
                (ans["setting"] == "home" and (
                    ans["lift"] in {
                        "floors_5_10", "floors_11_15", "floors_16_25",
                        "floors_26_40", "floors_41_60", "floors_above_60",
                    }
                    or ans["demand"] in {"large", "very_large", "bulk"}
                    or ans.get("c2_depth") in {
                        "300_450ft", "450_600ft", "600_800ft",
                        "800_1000ft", "above_1000ft",
                    }
                ))
                or ans["setting"] == "shop_small_comm"
            )

        if needs_phase_confirm:
            ans["c7_phase"] = render_question(
                "Additional detail",
                f"Power supply phase (default for this setting: {default_phase}-phase)",
                "c7_phase",
                C7_OPTIONS,
                ans,
                "Please confirm or override the default — small commercial connections vary.",
            )
        elif default_phase:
            ans["c7_phase"] = default_phase

        c8_triggered = (
            ans.get("setting") in {"farm", "light_industry", "large_commercial"}
            or ans.get("demand") in {"large", "very_large", "bulk"}
        )

        if c8_triggered:
            ans["c8_duty"] = render_question(
                "Additional detail",
                "Duty cycle (hours per day)",
                "c8_duty",
                C8_OPTIONS,
                ans,
            )

        if ans.get("c7_phase") == "Single":
            ans["c9_voltage"] = render_question(
                "Additional detail",
                "Lowest voltage at pump site",
                "c9_voltage",
                C9_OPTIONS,
                ans,
                "What is the lowest voltage you usually get at the pump site?",
            )

        show_soft_warnings(ans)

    answered, total_required = required_answer_count(ans)
    progress_pct = int((answered / total_required) * 100) if total_required else 0
    hero_slot.markdown("", unsafe_allow_html=True)
    with hero_slot:
        render_hero(progress_pct, sku_count)

    vec = None
    scored = None
    trace = []
    l_flags = []

    try:
        required_complete = answered == total_required and all(
            ans.get(k) is not None for k in ["job", "source", "lift", "demand", "setting"]
        )

        if required_complete and ans.get("c6_quality") != "industrial_effluent":
            vec = build_vector(ans)
            df = get_catalogue()
            survivors, trace = filter_skus(df, vec)
            scored = score_skus(survivors, vec)
            l_flags = lift_flags(ans)
    except Exception as exc:
        st.markdown(
            f'<div class="error-box">Could not calculate recommendations: {exc}</div>',
            unsafe_allow_html=True,
        )

    with right:
        st.markdown('<div class="side-stack">', unsafe_allow_html=True)

        st.button("Reset", on_click=reset_app)

        render_vector_panel(vec)

        for code, msg in l_flags:
            st.markdown(
                f'<div class="warning-box">ℹ <b>{code}:</b> {msg}</div>',
                unsafe_allow_html=True,
            )

        render_recommendations(scored, l_flags)

        if trace:
            with st.expander("Show filter trace"):
                for t in trace:
                    st.text(f"Step {t['step']} : {t['label']} → {t['rows_left']} rows")

        st.markdown('</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
