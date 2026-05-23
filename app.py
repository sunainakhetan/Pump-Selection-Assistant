"""Streamlit Pump Selection Assistant aligned to Framework v0.6."""

import os
from pathlib import Path
import pandas as pd
import streamlit as st

from rules import evaluate, is_disabled
from scoring import filter_skus, lift_flags, score_skus
from vector import SETTING_DEFAULTS, build_vector, c8_triggered, c9_variant, default_phase, needs_phase_confirm

st.set_page_config(page_title="Pump Selection Assistant", page_icon="💧", layout="wide", initial_sidebar_state="collapsed")
BASE_DIR = Path(__file__).parent
EXCEL_PATH = BASE_DIR / "FINAL_MASTER_DATASHEET_final.xlsx"

@st.cache_data(show_spinner=False)
def load_catalogue(path: str, mtime: float) -> pd.DataFrame:
    return pd.read_excel(path, sheet_name="Master Data")

def get_catalogue() -> pd.DataFrame:
    mtime = os.path.getmtime(EXCEL_PATH) if EXCEL_PATH.exists() else 0
    return load_catalogue(str(EXCEL_PATH), mtime)

css_path = BASE_DIR / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

SETTING_OPTIONS = [("home", "Home"), ("farm", "Farm / agriculture"), ("shop_small_comm", "Shop / office / small commercial"), ("large_commercial", "Large commercial or institutional"), ("light_industry", "Light industry / warehouse / construction site")]
JOB_OPTIONS = [("lift_and_store", "Lift and store"), ("lift_and_pressurise_directly", "Lift and pressurise directly"), ("boost_pressure", "Boost pressure from existing storage or supply"), ("drain_water", "Drain or remove water"), ("pump_sewage", "Pump out sewage or dirty water")]
SOURCE_OPTIONS = [("borewell", "Borewell"), ("open_well", "Open well or pond"), ("underground_sump", "Underground sump or storage tank"), ("overhead_tank", "Overhead tank"), ("municipal", "Municipal line / direct supply"), ("sewage_pit", "Sewage or drainage pit"), ("open_ground", "Open ground water (canal, river, farm channel)")]
LIFT_OPTIONS = [("ground", "Same level / No lift / Ground floor only"), ("floor_1", "1st floor (~3 m)"), ("floor_2", "2nd floor (~6 m)"), ("floor_3", "3rd floor (~9 m)"), ("floor_4", "4th floor (~12 m)"), ("floors_5_10", "5–10 floors (~15–30 m)"), ("floors_11_15", "11–15 floors (~33–45 m)"), ("floors_16_25", "16–25 floors (~48–75 m)"), ("floors_26_40", "26–40 floors (~78–120 m)"), ("floors_41_60", "41–60 floors (~123–180 m)"), ("floors_above_60", "Above 60 floors (above ~180 m)")]
DEMAND_OPTIONS_BY_SETTING = {
    "home": [("vol_200", "up to ~200 L/day — 1 resident"), ("vol_800", "~200–800 L/day — 2–5 residents"), ("vol_2000", "~800–2,000 L/day — 5–15 residents"), ("vol_5000", "~2,000–5,000 L/day — large independent home or small farmhouse")],
    "farm": [("vol_800", "up to ~800 L/day — homestead / no field irrigation"), ("vol_2000", "~800–2,000 L/day — larger homestead / backyard livestock"), ("vol_10000", "~2,000–10,000 L/day — very small irrigated plot or small dairy"), ("vol_50000", "~10,000–50,000 L/day — small-to-mid irrigated farm"), ("vol_200000", "~50,000–200,000 L/day — mid-to-large commercial farm"), ("vol_above_200000", "above ~200,000 L/day — large commercial farm / estate")],
    "shop_small_comm": [("vol_200", "up to ~200 L/day — kiosk or single-staff outlet"), ("vol_800", "~200–800 L/day — small shop or compact office"), ("vol_2000", "~800–2,000 L/day — mid-size office, clinic, or retail"), ("vol_5000", "~2,000–5,000 L/day — large office floor or small restaurant"), ("vol_10000", "~5,000–10,000 L/day — large standalone commercial premises")],
    "large_commercial": [("vol_5000", "~2,000–5,000 L/day — very small institutional premises"), ("vol_10000", "~5,000–10,000 L/day — small institutional premises"), ("vol_50000", "~10,000–50,000 L/day — mid-size institutional premises"), ("vol_200000", "~50,000–200,000 L/day — large institutional premises"), ("vol_above_200000", "above ~200,000 L/day — very large institutional premises")],
    "light_industry": [("vol_800", "~200–800 L/day — small workshop or storage shed"), ("vol_2000", "~800–2,000 L/day — small factory or warehouse"), ("vol_5000", "~2,000–5,000 L/day — mid-size factory or active site"), ("vol_10000", "~5,000–10,000 L/day — large factory or major construction"), ("vol_50000", "~10,000–50,000 L/day — mid-size industrial unit"), ("vol_200000", "~50,000–200,000 L/day — large industrial unit"), ("vol_above_200000", "above ~200,000 L/day — industrial estate or major project")],
}
DEST_OPTIONS = [("overhead_tank", "Overhead tank"), ("ground_sump", "Ground-level storage tank or sump"), ("direct_pipes", "Direct to building pipes (no tank)"), ("irrigation", "Irrigation lines / open field / livestock"), ("industrial_process", "Industrial process or treatment system"), ("tanker", "Tanker or external transfer point")]
C1_OPTIONS = [("casing_4in", "4 inch (100 mm)"), ("casing_6in", "6 inch (150 mm)"), ("casing_8in", "8 inch (200 mm)"), ("casing_10in", "10 inch (250 mm)"), ("casing_12in_plus", "12 inch (300 mm) and above")]
C2_OPTIONS = [("under_50ft", "Under 50 ft"), ("50_100ft", "50–100 ft"), ("100_200ft", "100–200 ft"), ("200_300ft", "200–300 ft"), ("300_450ft", "300–450 ft"), ("450_600ft", "450–600 ft"), ("600_800ft", "600–800 ft"), ("800_1000ft", "800–1,000 ft"), ("above_1000ft", "Above 1,000 ft")]
C3_OPTIONS = [("shallow_under_30ft", "Shallow open well (under 30 ft)"), ("medium_30_60ft", "Medium (30–60 ft)"), ("deep_above_60ft", "Deep open well (above 60 ft)")]
C4_OPTIONS = [("1_4", "1–4 outlets", 2), ("5_12", "5–12 outlets", 8), ("13_20", "13–20 outlets", 16), ("21_35", "21–35 outlets", 28), ("36_75", "36–75 outlets", 55), ("76_150", "76–150 outlets", 113), ("above_150", "More than 150 outlets", 200)]
C5_OPTIONS = [("light", "Light"), ("moderate", "Moderate"), ("heavy", "Heavy"), ("constant_peak", "Constant peak")]
C6_OPTIONS = [("clean_water", "Clean water"), ("lightly_soiled", "Lightly soiled"), ("solids_waste", "Solids and waste"), ("heavy_sewage", "Heavy sewage"), ("industrial_effluent", "Industrial effluent")]
C7_OPTIONS = [("Single", "Single-phase"), ("Three", "Three-phase")]
C8_OPTIONS = [("moderate", "Moderate (2–6 hours/day)"), ("heavy", "Heavy (6–12 hours/day)"), ("continuous", "Continuous (12+ hours/day)")]
C9_BAND_OPTIONS = [("single_low_under_200", "Below 200 V (Low Voltage)"), ("single_normal_200_240", "200–240 V (Normal Voltage)")]
THREE_MIN_OPTIONS = [(v, f"{v} V") for v in [340, 350, 360, 370, 380, 390, 400, 410]]
THREE_MAX_OPTIONS = [(v, f"{v} V") for v in [380, 390, 400, 410, 420, 430, 440]]
FARM_SINGLE_MIN_OPTIONS = [(v, f"{v} V") for v in [140, 150, 160, 170, 180, 190, 200, 210, 220]]
FARM_SINGLE_MAX_OPTIONS = [(v, f"{v} V") for v in [190, 200, 210, 220, 230, 240]]
C5A_BY_SETTING = {
    "home": [("home_standard", "Standard fittings — taps, showers, WCs, kitchen"), ("home_premium", "Premium fittings — rain shower, body jets, or large overhead shower")],
    "shop_small_comm": [("shop_standard", "Standard fittings — taps, WCs, pantry, basic washrooms"), ("shop_premium", "Premium fittings — salon, spa, boutique-hotel showers, or clinic rinse points")],
    "large_commercial": [("large_comm_standard", "Standard fittings only — taps, WCs, pantries"), ("large_comm_premium", "Premium guest-room, spa, or pool-deck fittings")],
    "farm": [("farm_flood", "Flood, furrow, or hand-watering only"), ("farm_drip", "Drip irrigation or livestock troughs"), ("farm_sprinkler", "Sprinklers or general wash-down"), ("farm_rain_gun", "Rain guns or high-pressure sprinklers")],
    "light_industry": [("industry_standard", "Standard washroom and canteen use only"), ("industry_light_wash", "Light wash-down"), ("industry_routine_wash", "Routine production wash"), ("industry_heavy_jetting", "Heavy wash-down or high-pressure jetting")],
}
FIELD_ORDER = ["setting", "job", "source", "lift", "demand", "c0_destination", "c1_casing", "c2_depth", "c3_well_depth", "c4_outlets", "c4_outlets_count", "c5_usage", "c5a_pressure", "c6_quality", "c7_phase", "c8_duty", "c9_voltage_band", "c9_min_v", "c9_max_v"]
PRESSURE_JOBS = {"boost_pressure", "lift_and_pressurise_directly"}
DESCRIPTIONS = {"setting": "Setting comes first in Framework v0.6 because it controls demand bands, phase defaults, and C5a/C9 variants."}

def init_state():
    if "answers" not in st.session_state:
        st.session_state.answers = {}

def current_answers():
    return dict(st.session_state.answers)

def reset_app():
    st.session_state.answers = {}
    for key in list(st.session_state.keys()):
        if key.startswith("select_") or key == "rec_search":
            del st.session_state[key]

def set_answer(field, value, payload=None):
    ans = dict(st.session_state.answers)
    if ans.get(field) != value and field in FIELD_ORDER:
        for downstream in FIELD_ORDER[FIELD_ORDER.index(field):]:
            ans.pop(downstream, None)
    ans[field] = value
    if field == "c4_outlets":
        ans["c4_outlets_count"] = payload
    st.session_state.answers = ans

def render_option(field, opt, ans):
    oid, label = opt[0], opt[1]
    payload = opt[2] if len(opt) > 2 else None
    disabled, reason = is_disabled(field, oid, ans)
    selected = ans.get(field) == oid
    classes = ["option-card"] + (["selected"] if selected else []) + (["disabled"] if disabled else [])
    selected_html = '<div class="selected-pill">Selected</div>' if selected else ''
    reason_html = f'<div class="option-reason">Unavailable: {reason}</div>' if disabled and reason else ''
    st.markdown(f'<div class="{" ".join(classes)}"><div class="option-label">{label}</div><div class="option-desc"></div>{selected_html}{reason_html}</div>', unsafe_allow_html=True)
    st.button("Selected" if selected else "Select", key=f"select_{field}_{oid}", disabled=disabled or selected, on_click=set_answer, args=(field, oid, payload), use_container_width=True)

def render_question(step, title, field, options, help_text=""):
    ans = current_answers()
    st.markdown('<div class="question-panel">', unsafe_allow_html=True)
    st.markdown(f'<div class="step-badge">{step}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)
    if help_text:
        st.markdown(f'<div class="section-help">{help_text}</div>', unsafe_allow_html=True)
    st.markdown('<div class="option-grid">', unsafe_allow_html=True)
    for opt in options:
        render_option(field, opt, ans)
    st.markdown('</div></div>', unsafe_allow_html=True)

def required_fields(ans):
    fields = ["setting"]
    if ans.get("setting"):
        fields += ["job", "source", "lift", "demand"]
    if ans.get("job") in {"lift_and_store", "lift_and_pressurise_directly"}:
        fields += ["c0_destination"]
    if ans.get("source") == "borewell":
        fields += ["c1_casing", "c2_depth"]
    if ans.get("source") == "open_well":
        fields += ["c3_well_depth"]
    if ans.get("job") in PRESSURE_JOBS:
        fields += ["c4_outlets", "c5_usage", "c5a_pressure"]
    if ans.get("job") in {"drain_water", "pump_sewage"}:
        fields += ["c6_quality"]
    if ans.get("setting") and ans.get("lift") and ans.get("demand") and needs_phase_confirm(ans):
        fields += ["c7_phase"]
    if ans.get("setting") and ans.get("demand") and c8_triggered(ans):
        fields += ["c8_duty"]
    phase = ans.get("c7_phase") or (default_phase(ans["setting"]) if ans.get("setting") else None)
    if ans.get("setting") and phase:
        fields += ["c9_voltage_band"] if c9_variant(ans["setting"], phase) == "single_band" else ["c9_min_v", "c9_max_v"]
    return fields

def auto_fill_phase(ans):
    ans = dict(ans)
    if ans.get("setting") and "c7_phase" not in ans and not needs_phase_confirm(ans):
        ans["c7_phase"] = SETTING_DEFAULTS[ans["setting"]][0]
    return ans

def is_complete(ans):
    fields = required_fields(ans)
    return all(ans.get(f) is not None for f in fields), fields

def render_hero(progress_pct, sku_count):
    st.markdown(f'''<div class="hero-shell"><div class="hero-grid"><div><div class="hero-badge">💧 Pump-selection assistant</div><div class="hero-title">Choose a pump from the updated catalogue.</div><p class="hero-copy">Answer a few questions and get the best-matching pumps from the current SKU catalogue. The matcher follows Framework v0.6, including setting-specific demand, C5a, and revised C9 voltage logic.</p></div><div class="status-card"><div class="status-row"><span>Progress</span><span>{progress_pct}%</span></div><div class="progress-rail"><span class="progress-fill" style="width:{progress_pct}%"></span></div><div class="pill-row"><span class="ui-pill">{sku_count:,} SKUs loaded</span><span class="ui-pill">v0.6 rules enabled</span></div></div></div></div>''', unsafe_allow_html=True)

def render_c9(ans):
    phase = ans.get("c7_phase") or default_phase(ans["setting"])
    variant = c9_variant(ans["setting"], phase)
    if variant == "single_band":
        render_question("Additional detail", "Voltage at pump site", "c9_voltage_band", C9_BAND_OPTIONS, "Home / small-commercial single-phase uses the two-band C9 picker.")
    elif variant == "farm_single_range":
        render_question("Additional detail", "Lowest single-phase voltage", "c9_min_v", FARM_SINGLE_MIN_OPTIONS)
        render_question("Additional detail", "Highest single-phase voltage", "c9_max_v", FARM_SINGLE_MAX_OPTIONS)
    else:
        render_question("Additional detail", "Lowest three-phase voltage", "c9_min_v", THREE_MIN_OPTIONS)
        render_question("Additional detail", "Highest three-phase voltage", "c9_max_v", THREE_MAX_OPTIONS)

def show_soft_warnings(ans):
    for rid, sev, reason in evaluate(ans):
        if sev == "soft":
            st.markdown(f'<div class="warning-box">⚠ Rule #{rid}: {reason}</div>', unsafe_allow_html=True)

def render_vector_panel(vec):
    st.markdown('<div class="side-panel">', unsafe_allow_html=True)
    st.markdown('<h2 class="side-title">Requirement vector</h2><p class="side-subtitle">Live hydraulic target used by the matcher.</p>', unsafe_allow_html=True)
    if not vec:
        st.markdown('<div class="empty-card">Complete the questions to build the vector.</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="metric-grid">', unsafe_allow_html=True)
        metrics = [("Pump types", ", ".join(vec["allowed_pump_types"]) or "None", "Allowed set"), ("Head", f"{vec['required_min_head']:.0f} / {vec['typical_head']:.0f} m", "Min / typical"), ("Flow", f"{vec['required_min_flow']:.0f} / {vec['typical_flow']:.0f} LPH", "Min / typical"), ("Phase", vec["final_phase"], "Final C7")]
        for label, value, sub in metrics:
            st.markdown(f'<div class="metric-card"><small>{label}</small><strong>{value}</strong><span>{sub}</span></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        with st.expander("Raw vector"):
            st.json(vec)
    st.markdown('</div>', unsafe_allow_html=True)

def fmt_range(row, a, b, suffix=""):
    return f"{row.get(a, '—')}–{row.get(b, '—')}{suffix}"

def render_card(rank, row):
    flags = row.get("flags", []) if isinstance(row.get("flags", []), list) else []
    flag_html = ''.join(f'<span class="flag-pill">{f}</span>' for f in flags)
    st.markdown(f'''<div class="rec-card"><div class="rec-top"><div><div class="brand-sku"><span class="rank">#{rank}</span>{row.get('Brand','')} {row.get('SKU','')}</div><div class="type-line">{row.get('Type','')} · {row.get('Subtype','')}</div></div><div class="score-pill">{int(row.get('score',0))}</div></div><div class="specs"><div class="spec-box"><div class="spec-label">HP</div><div class="spec-value">{row.get('HP','—')}</div></div><div class="spec-box"><div class="spec-label">Phase</div><div class="spec-value">{row.get('Phase','—')}</div></div><div class="spec-box"><div class="spec-label">Head</div><div class="spec-value">{fmt_range(row, 'Min Head (m)', 'Max Head (m)', ' m')}</div></div><div class="spec-box"><div class="spec-label">Flow</div><div class="spec-value">{fmt_range(row, 'Min Flow (LPH)', 'Max Flow (LPH)', ' LPH')}</div></div></div>{flag_html}</div>''', unsafe_allow_html=True)

def render_recommendations(scored):
    st.markdown('<div class="side-panel">', unsafe_allow_html=True)
    st.markdown('<h2 class="side-title">Recommendations</h2><p class="side-subtitle">Top matches from the updated catalogue.</p>', unsafe_allow_html=True)
    if scored is None:
        st.markdown('<div class="empty-card">Recommendations appear after all required answers are complete.</div>', unsafe_allow_html=True)
    elif len(scored) == 0:
        st.markdown('<div class="empty-card">No SKUs survived the current filters.</div>', unsafe_allow_html=True)
    else:
        search = st.text_input("Search recommendations", key="rec_search", placeholder="Brand or SKU")
        view = scored
        if search:
            mask = view["Brand"].astype(str).str.contains(search, case=False, na=False) | view["SKU"].astype(str).str.contains(search, case=False, na=False)
            view = view[mask]
        for i, (_, row) in enumerate(view.head(5).iterrows(), 1):
            render_card(i, row)
    st.markdown('</div>', unsafe_allow_html=True)

def main():
    init_state()
    try: sku_count = len(get_catalogue())
    except Exception: sku_count = 0
    progress_ans = auto_fill_phase(current_answers())
    complete, fields = is_complete(progress_ans)
    progress_pct = int(sum(1 for f in fields if progress_ans.get(f) is not None) / len(fields) * 100) if fields else 0
    render_hero(progress_pct, sku_count)

    left, right = st.columns([1.85, 1], gap="large")
    with left:
        render_question("Step 1 of 5 · Setting", "What kind of place is it?", "setting", SETTING_OPTIONS, DESCRIPTIONS["setting"])
        ans = current_answers()
        if ans.get("setting"):
            render_question("Step 2 of 5 · Job", "What is the pump supposed to do?", "job", JOB_OPTIONS)
            render_question("Step 3 of 5 · Source", "Where is the water coming from?", "source", SOURCE_OPTIONS)
            render_question("Step 4 of 5 · Lift", "How high does the water need to go?", "lift", LIFT_OPTIONS)
            render_question("Step 5 of 5 · Demand", "How much water is needed?", "demand", DEMAND_OPTIONS_BY_SETTING[ans["setting"]], "Demand bands are setting-specific; internally they map to representative daily volume.")
        ans = current_answers()
        if ans.get("job") in {"lift_and_store", "lift_and_pressurise_directly"}: render_question("Additional detail", "Where does the water end up?", "c0_destination", DEST_OPTIONS)
        ans = current_answers()
        if ans.get("source") == "borewell":
            render_question("Additional detail", "Borewell casing diameter", "c1_casing", C1_OPTIONS)
            render_question("Additional detail", "Borewell water depth (static rest level)", "c2_depth", C2_OPTIONS, "Depth to top of water column when the pump is off — not drilled depth.")
        ans = current_answers()
        if ans.get("source") == "open_well": render_question("Additional detail", "Open well water depth", "c3_well_depth", C3_OPTIONS)
        ans = current_answers()
        if ans.get("job") in PRESSURE_JOBS:
            render_question("Additional detail", "Number of outlets", "c4_outlets", C4_OPTIONS)
            render_question("Additional detail", "How simultaneously are outlets used?", "c5_usage", C5_OPTIONS)
            if ans.get("setting"): render_question("Additional detail", "Fixture / application pressure class", "c5a_pressure", C5A_BY_SETTING[ans["setting"]], "C5a adds pressure head; for small homes with premium fittings it also applies a flow floor.")
        ans = current_answers()
        if ans.get("job") in {"drain_water", "pump_sewage"}:
            render_question("Additional detail", "Water quality / contents", "c6_quality", C6_OPTIONS)
            if ans.get("c6_quality") == "industrial_effluent": st.markdown('<div class="error-box">⚠ <b>Specialised pump required.</b> Industrial effluent is outside catalogue scope.</div>', unsafe_allow_html=True)
        ans = current_answers()
        if ans.get("setting") and ans.get("lift") and ans.get("demand"):
            if needs_phase_confirm(ans): render_question("Additional detail", f"Power supply phase (default: {default_phase(ans['setting'])}-phase)", "c7_phase", C7_OPTIONS)
            elif "c7_phase" not in ans: set_answer("c7_phase", default_phase(ans["setting"]))
        ans = current_answers()
        if ans.get("setting") and ans.get("demand") and c8_triggered(ans): render_question("Additional detail", "Duty cycle (hours per day)", "c8_duty", C8_OPTIONS)
        ans = auto_fill_phase(current_answers())
        if ans.get("setting") and ans.get("c7_phase"): render_c9(ans)
        show_soft_warnings(auto_fill_phase(current_answers()))

    final_ans = auto_fill_phase(current_answers())
    complete, _ = is_complete(final_ans)
    vec = scored = None
    trace = []
    l_flags = []
    try:
        if complete and final_ans.get("c6_quality") != "industrial_effluent":
            vec = build_vector(final_ans)
            survivors, trace = filter_skus(get_catalogue(), vec)
            scored = score_skus(survivors, vec)
            l_flags = lift_flags(final_ans)
    except Exception as exc:
        st.markdown(f'<div class="error-box">Could not calculate recommendations: {exc}</div>', unsafe_allow_html=True)

    with right:
        st.markdown('<div class="side-stack">', unsafe_allow_html=True)
        st.button("Reset", on_click=reset_app)
        render_vector_panel(vec)
        for code, msg in l_flags: st.markdown(f'<div class="warning-box">ℹ <b>{code}:</b> {msg}</div>', unsafe_allow_html=True)
        render_recommendations(scored)
        if trace:
            with st.expander("Show filter trace"):
                for t in trace: st.text(f"Step {t['step']} : {t['label']} → {t['rows_left']} rows")
        st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
