"""Streamlit Pump Selection Assistant aligned to Framework v1.1."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

import pandas as pd
import streamlit as st

from rules import evaluate
from scoring import filter_skus, lift_flags, score_skus
from vector import (
    C5A_HEAD_ADD,
    DRAIN_FLOW,
    JOBS,
    LOW_C9_BAND,
    MATRIX,
    NORMAL_C9_BAND,
    SETTINGS,
    SOURCES,
    available_destinations,
    available_jobs,
    available_sources,
    allowed_c9_max_values,
    allowed_c9_min_values,
    c8_triggered,
    c9_variant,
    construction_drain_lift_triggered,
    default_phase,
    final_phase,
    lift_triggered,
    needs_phase_confirm,
    source_depth_field,
    build_vector,
)

# ---------------------------------------------------------------------------
# Page config and catalogue loader
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Pump Selection Assistant",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="collapsed",
)

BASE_DIR = Path(__file__).parent
CATALOGUE_CANDIDATES = [
    BASE_DIR / "FINAL_MASTER_DATASHEET_final.xlsx",
    BASE_DIR / "MASTER DATASHEET_final_final copy(13).xlsx",
    BASE_DIR / "MASTER DATASHEET_final_final copy(7).xlsx",
]


def resolve_catalogue_path() -> Path:
    for path in CATALOGUE_CANDIDATES:
        if path.exists():
            return path
    return CATALOGUE_CANDIDATES[0]


@st.cache_data(show_spinner=False)
def load_catalogue(path: str, mtime: float) -> pd.DataFrame:
    return pd.read_excel(path, sheet_name="Master Data")


def get_catalogue() -> pd.DataFrame:
    path = resolve_catalogue_path()
    mtime = os.path.getmtime(path) if path.exists() else 0
    return load_catalogue(str(path), mtime)


css_path = BASE_DIR / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

COMPACT_CARD_CSS = """
<style>
[class*="st-key-optwrap_"] .stButton { height: 100%; }
[class*="st-key-optwrap_"] .stButton > button {
  min-height: 218px !important; height:auto !important; width:100% !important;
  padding:26px 30px !important; border-radius:24px !important; text-align:left !important;
  white-space:normal !important; line-height:1.36 !important; font-size:1.02rem !important;
  font-weight:500 !important; background:#ffffff !important; border:1px solid var(--line,#e2e8f0) !important;
  color:var(--ink,#0f172a) !important; box-shadow:none !important; display:flex !important;
  align-items:flex-start !important; justify-content:flex-start !important; overflow:visible !important;
}
[class*="st-key-optwrap_"] .stButton > button div,
[class*="st-key-optwrap_"] .stButton > button p { width:100% !important; margin:0 !important; padding:0 !important; text-align:left !important; white-space:normal !important; overflow-wrap:anywhere !important; word-break:normal !important; }
[class*="st-key-optwrap_"] .stButton > button strong { display:block !important; margin-bottom:18px !important; font-size:calc(1.02rem + 2pt) !important; line-height:1.24 !important; font-weight:900 !important; color:var(--ink,#0f172a) !important; }
[class*="st-key-optwrap_"] .stButton > button:hover:not(:disabled) { border-color:#67e8f9 !important; background:#f8fafc !important; transform:translateY(-1px); }
[class*="st-key-optwrap_"] .stButton > button:disabled { background:#f8fafc !important; color:#94a3b8 !important; border-color:#e2e8f0 !important; }
[class*="st-key-optwrap_"] .stButton > button:disabled strong { color:#94a3b8 !important; }
.compact-question-panel { padding-bottom:18px; }
.detailed-rec-card { padding:16px; }
.detailed-specs { grid-template-columns:repeat(3,minmax(0,1fr)) !important; }
.detailed-specs .spec-box { min-height:62px; }
.input-note { padding:12px 14px; border:1px solid var(--line,#e2e8f0); background:#f8fafc; border-radius:16px; color:#475569; font-weight:700; margin:8px 0 10px; }
.warning-pill { display:inline-flex; align-items:center; margin:8px 0 14px 0; padding:10px 14px; border-radius:999px; background:#fff7ed; border:1px solid #fed7aa; color:#9a3412; font-weight:750; font-size:.86rem; line-height:1.25; }
@media(max-width:1100px) { .detailed-specs { grid-template-columns:repeat(2,minmax(0,1fr)) !important; } }
@media(max-width:700px) { .detailed-specs { grid-template-columns:1fr !important; } [class*="st-key-optwrap_"] .stButton > button { min-height:170px !important; padding:22px 24px !important; } }
</style>
"""
st.markdown(COMPACT_CARD_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Options and descriptions
# ---------------------------------------------------------------------------

SETTING_OPTIONS = [
    ("home", SETTINGS["home"]),
    ("farm", SETTINGS["farm"]),
    ("shop_small_comm", SETTINGS["shop_small_comm"]),
    ("large_commercial", SETTINGS["large_commercial"]),
    ("light_industry", SETTINGS["light_industry"]),
]

JOB_OPTIONS = [(k, v) for k, v in JOBS.items()]

SOURCE_OPTIONS = [(k, v) for k, v in SOURCES.items() if k != "sewage_pit"] + [("sewage_pit", SOURCES["sewage_pit"])]

DEST_OPTIONS = [
    ("overhead_tank", "Overhead tank"),
    ("ground_sump", "Ground-level storage tank or sump"),
    ("direct_pipes", "Direct to building pipes"),
    ("irrigation", "Irrigation lines / open field / livestock"),
    ("industrial_process", "Industrial process or treatment system"),
]

LIFT_OPTIONS = [
    ("ground", "Same level / no lift / ground floor only"),
    ("floor_1", "1st floor (~3 m)"),
    ("floor_2", "2nd floor (~6 m)"),
    ("floor_3", "3rd floor (~9 m)"),
    ("floor_4", "4th floor (~12 m)"),
    ("floors_5_10", "5–10 floors (~30 m)"),
    ("floors_11_15", "11–15 floors (~45 m)"),
    ("floors_16_25", "16–25 floors (~75 m)"),
    ("floors_26_40", "26–40 floors (~120 m)"),
    ("floors_41_60", "41–60 floors (~180 m)"),
    ("floors_above_60", "Above 60 floors (custom engineering)"),
]

DEMAND_OPTIONS_BY_SETTING = {
    "home": [
        ("vol_200", "up to ~200 L/day — 1 resident"),
        ("vol_800", "~200–800 L/day — 2–5 residents"),
        ("vol_2000", "~800–2,000 L/day — 5–15 residents"),
        ("vol_5000", "~2,000–5,000 L/day — large independent home or small farmhouse"),
    ],
    "farm": [
        ("vol_800", "up to ~800 L/day — homestead / no field irrigation"),
        ("vol_2000", "~800–2,000 L/day — larger homestead / backyard livestock"),
        ("vol_10000", "~2,000–10,000 L/day — very small irrigated plot or small dairy"),
        ("vol_50000", "~10,000–50,000 L/day — small-to-mid irrigated farm"),
        ("vol_200000", "~50,000–200,000 L/day — mid-to-large commercial farm"),
        ("vol_above_200000", "above ~200,000 L/day — large commercial farm / estate"),
    ],
    "shop_small_comm": [
        ("vol_200", "up to ~200 L/day — kiosk or single-staff outlet"),
        ("vol_800", "~200–800 L/day — small shop or compact office"),
        ("vol_2000", "~800–2,000 L/day — mid-size office, clinic, or retail"),
        ("vol_5000", "~2,000–5,000 L/day — large office floor or small restaurant"),
        ("vol_10000", "~5,000–10,000 L/day — large standalone commercial premises"),
    ],
    "large_commercial": [
        ("vol_5000", "~2,000–5,000 L/day — very small institutional premises"),
        ("vol_10000", "~5,000–10,000 L/day — small institutional premises"),
        ("vol_50000", "~10,000–50,000 L/day — mid-size institutional premises"),
        ("vol_200000", "~50,000–200,000 L/day — large institutional premises"),
        ("vol_above_200000", "above ~200,000 L/day — very large institutional premises"),
    ],
    "light_industry": [
        ("vol_800", "~200–800 L/day — small workshop or storage shed"),
        ("vol_2000", "~800–2,000 L/day — small factory or warehouse"),
        ("vol_5000", "~2,000–5,000 L/day — mid-size factory or active site"),
        ("vol_10000", "~5,000–10,000 L/day — large factory or major construction"),
        ("vol_50000", "~10,000–50,000 L/day — mid-size industrial unit"),
        ("vol_200000", "~50,000–200,000 L/day — large industrial unit"),
        ("vol_above_200000", "above ~200,000 L/day — industrial estate or major project"),
    ],
}

DRAIN_RATE_OPTIONS = [
    ("trickle", "Trickle / occasional seepage"),
    ("routine_small", "Routine small drainage"),
    ("steady_moderate", "Steady moderate flow"),
    ("heavy_flow", "Heavy flow"),
    ("very_heavy", "Very heavy / continuous dewatering"),
    ("industrial_large", "Industrial / large-scale dewatering"),
]

C1_OPTIONS = [
    ("casing_4in", "4 inch (100 mm)"),
    ("casing_6in", "6 inch (150 mm)"),
    ("casing_8in", "8 inch (200 mm)"),
    ("casing_10in", "10 inch (250 mm)"),
    ("casing_12in_plus", "12 inch (300 mm) and above"),
]

C4_OPTIONS = [
    ("1_4", "1–4 outlets"),
    ("5_12", "5–12 outlets"),
    ("13_20", "13–20 outlets"),
    ("21_35", "21–35 outlets"),
    ("36_75", "36–75 outlets"),
    ("76_150", "76–150 outlets"),
    ("above_150", "More than 150 outlets"),
]

C5_OPTIONS = [
    ("light", "Light — most outlets used one at a time"),
    ("moderate", "Moderate — about half the outlets together"),
    ("heavy", "Heavy — many outlets together"),
    ("constant_peak", "Constant peak — full simultaneous demand"),
]

C5A_BY_SETTING = {
    "home": [("home_standard", "Standard fittings"), ("home_premium", "Premium fittings — rain shower, body jets, large overhead shower")],
    "shop_small_comm": [("shop_standard", "Standard fittings"), ("shop_premium", "Premium fittings — salon, spa, boutique-hotel showers")],
    "large_commercial": [("large_comm_standard", "Standard fittings only"), ("large_comm_premium", "Premium guest-room, spa, or pool-deck fittings")],
    "farm": [("farm_flood", "Flood, furrow, or hand-watering"), ("farm_drip", "Drip irrigation or livestock troughs"), ("farm_sprinkler", "Sprinklers or general wash-down"), ("farm_rain_gun", "Rain guns / high-pressure sprinklers")],
    "light_industry": [("industry_standard", "Standard washroom and canteen use only"), ("industry_light_wash", "Light wash-down"), ("industry_routine_wash", "Routine production wash"), ("industry_heavy_jetting", "Heavy wash-down or high-pressure jetting")],
}

C6_OPTIONS = [
    ("clean_water", "Clean water"),
    ("lightly_soiled", "Lightly soiled / grey water"),
    ("solids_waste", "Solids and waste"),
    ("heavy_sewage", "Heavy sewage"),
]

C7_OPTIONS = [("Single", "Single-phase"), ("Three", "Three-phase")]
C8_OPTIONS = [("moderate", "Moderate (2–6 h/day)"), ("heavy", "Heavy (6–12 h/day)"), ("continuous", "Continuous (12+ h/day)")]
C9_BAND_OPTIONS = [(LOW_C9_BAND, "Below 200 V (Low Voltage)"), (NORMAL_C9_BAND, "200–240 V (Normal Voltage)")]

OPTION_DESCRIPTIONS = {
    "setting": {
        "home": "Any residence — independent house, villa, flat, farmhouse.",
        "farm": "Irrigation, crop watering, livestock, agricultural property.",
        "shop_small_comm": "Showrooms, small offices, clinics, restaurants, small retail.",
        "large_commercial": "Hotels, hospitals, schools, hostels, apartment blocks, colleges.",
        "light_industry": "Factories, warehouses, construction projects, light manufacturing.",
    },
    "job": {
        "lift_and_store": "Pull water from an enabled source and fill an overhead tank or ground-level storage tank / sump.",
        "boost_pressure": "Deliver water under pressure to building pipes, irrigation / livestock lines, or an industrial process.",
        "drain_sewage": "Empty a sewage or drainage pit. The pump family is always Sewage; C6 decides cutter logic.",
    },
    "source": {
        "borewell": "Deep underground source with a narrow casing pipe. Triggers C1 and C2.",
        "open_well": "Open water body, accessible from the top. Triggers C3.",
        "open_ground": "Canal, river, or farm channel. Triggers C3G and the 7 m rule.",
        "underground_sump": "Ground-level or below-ground tank already holding water. Adds fixed +3 m sump allowance.",
        "overhead_tank": "Tank already at height. Appears only as a Boost-pressure source.",
        "municipal": "External piped or shared-society line, used only for storage fill to a ground sump.",
        "sewage_pit": "Auto source for Drain sewage / water.",
    },
    "c0_destination": {
        "overhead_tank": "Storage destination. Triggers the lift question.",
        "ground_sump": "Storage at ground or below-ground level. Lift is not asked.",
        "direct_pipes": "Pressure delivery to building plumbing. Triggers lift and pressure cluster.",
        "irrigation": "Farm-only pressure delivery. Lift is not asked; C4/C5/C5a still apply.",
        "industrial_process": "Large-commercial / light-industry process delivery. Triggers lift and pressure cluster.",
    },
    "lift": {
        "ground": "0 m above-ground lift.",
        "floor_1": "Representative lift 3 m.",
        "floor_2": "Representative lift 6 m.",
        "floor_3": "Representative lift 9 m.",
        "floor_4": "Representative lift 12 m.",
        "floors_5_10": "Representative lift 30 m.",
        "floors_11_15": "Representative lift 45 m.",
        "floors_16_25": "Representative lift 75 m; staged pumping usually recommended.",
        "floors_26_40": "Representative lift 120 m; multi-zone scheme likely.",
        "floors_41_60": "Representative lift 180 m; consultant review recommended.",
        "floors_above_60": "Custom engineering normally required.",
    },
    "c1_casing": {
        "casing_4in": "Eligible V-codes: V3, V3.5, V4.",
        "casing_6in": "Eligible V-codes: V3, V3.5, V4, V5, V6.",
        "casing_8in": "Eligible V-codes: V6, V7, V8.",
        "casing_10in": "Eligible V-codes: V8, V9.",
        "casing_12in_plus": "Eligible V-codes: V12 and above.",
    },
    "c4_outlets": {
        "1_4": "Small fixture set.",
        "5_12": "Small home / compact office fixture set.",
        "13_20": "Large home or small commercial.",
        "21_35": "Hotel floor, clinic, farm shed, or small institution.",
        "36_75": "Mid-size hotel, hostel, dairy, or office floor.",
        "76_150": "Large hotel, apartment block, institution, or farm use.",
        "above_150": "Large complex, campus, estate, or industrial use.",
    },
    "c5_usage": {
        "light": "Multiplier ×0.3.",
        "moderate": "Multiplier ×0.5.",
        "heavy": "Multiplier ×0.7.",
        "constant_peak": "Multiplier ×1.0.",
    },
    "c6_quality": {
        "clean_water": "Uses a non-cutter Sewage pump.",
        "lightly_soiled": "Grey water; uses a non-cutter Sewage pump.",
        "solids_waste": "Cutter required.",
        "heavy_sewage": "Cutter mandatory; non-cutter rows excluded.",
    },
    "c7_phase": {"Single": "230 V class.", "Three": "415 V class."},
    "c8_duty": {"moderate": "4 h used in flow calculation.", "heavy": "9 h used in flow calculation.", "continuous": "14 h used in flow calculation."},
    "c9_voltage_band": {LOW_C9_BAND: "Supply commonly sags below 200 V.", NORMAL_C9_BAND: "Standard light-duty supply."},
}

FIELD_ORDER = [
    "setting", "job", "source", "c0_destination", "lift", "construction_lift_m",
    "c1_casing", "c2_depth_m", "c3_depth_m", "c3g_depth_m", "demand", "drain_rate",
    "c4_outlets", "c5_usage", "c5a_pressure", "c6_quality", "water_scarce", "c7_phase",
    "c8_duty", "c9_voltage_band", "c9_min_v", "c9_max_v",
]

# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------


def init_state():
    if "answers" not in st.session_state:
        st.session_state.answers = {}


def current_answers() -> dict:
    ans = dict(st.session_state.answers)
    if ans.get("job") == "drain_sewage":
        ans["source"] = "sewage_pit"
        ans["c0_destination"] = None
    return ans


def reset_app():
    st.session_state.answers = {}
    for key in list(st.session_state.keys()):
        if key.startswith(("select_", "optwrap_", "slider_")) or key in {"rec_search", "water_scarce_checkbox"}:
            del st.session_state[key]


def set_answer(field, value, payload=None):
    ans = dict(st.session_state.answers)
    previous = ans.get(field)
    if previous != value and field in FIELD_ORDER:
        for downstream in FIELD_ORDER[FIELD_ORDER.index(field):]:
            ans.pop(downstream, None)
    ans[field] = value
    if field == "job" and value == "drain_sewage":
        ans["source"] = "sewage_pit"
        ans["c0_destination"] = None
    st.session_state.answers = ans


def set_numeric(field: str, value):
    ans = dict(st.session_state.answers)
    ans[field] = value
    st.session_state.answers = ans

# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------


def option_description(field: str, option_id) -> str:
    ans = current_answers()
    if field == "demand":
        return demand_description(ans.get("setting"), option_id)
    if field == "drain_rate":
        req, typ = DRAIN_FLOW[option_id]
        return f"Required flow {req:,} LPH; typical {typ:,} LPH."
    if field == "c5a_pressure":
        add = C5A_HEAD_ADD.get(option_id, 0)
        return f"Head add-on +{add} m."
    if field in {"c9_min_v", "c9_max_v"}:
        return "The pump's voltage envelope must contain this site range."
    return OPTION_DESCRIPTIONS.get(field, {}).get(option_id, "")


def demand_description(setting: str | None, option_id: str) -> str:
    text = {
        "vol_200": "Smallest daily-use band.",
        "vol_800": "Compact premises / small homestead band.",
        "vol_2000": "Small-to-mid daily-use band.",
        "vol_5000": "Large home or small commercial / institutional band.",
        "vol_10000": "Upper small-commercial or industrial band.",
        "vol_50000": "Mid-size institutional, farm, or industrial band.",
        "vol_200000": "Large institutional, farm, or industrial band.",
        "vol_above_200000": "Very large site; may need engineering review.",
    }.get(option_id, "")
    return text


def disabled_reason_for_candidate(field: str, candidate_value, ans: dict):
    if field == "job" and ans.get("setting"):
        if candidate_value not in available_jobs(ans["setting"]):
            return "Not enabled for this Setting."
    if field == "source" and ans.get("setting") and ans.get("job"):
        if candidate_value not in available_sources(ans["setting"], ans["job"]):
            return "Not enabled by the Setting × Job matrix."
    if field == "c0_destination" and ans.get("setting") and ans.get("job") and ans.get("source"):
        if candidate_value not in available_destinations(ans["setting"], ans["job"], ans["source"]):
            return "Not enabled by the Setting × Job × Source matrix."
    if field == "c9_max_v" and ans.get("c9_min_v") is not None:
        if candidate_value <= ans["c9_min_v"]:
            return "Max V must be greater than Min V."
    return None


def render_option(field: str, opt, ans: dict, force_disabled_reason: str | None = None):
    oid, label = opt[0], opt[1]
    reason = disabled_reason_for_candidate(field, oid, ans)
    disabled = reason is not None
    if force_disabled_reason:
        disabled = True
        reason = force_disabled_reason
    selected = ans.get(field) == oid
    desc = option_description(field, oid)
    button_label = f"{'✓ ' if selected else ''}**{label}**"
    if desc:
        button_label += f"\n\n{desc}"
    if disabled and reason:
        button_label += f"\n\nUnavailable: {reason}"
    safe_oid = str(oid).replace("-", "_").replace(".", "_").replace(" ", "_").replace("/", "_")
    wrapper_key = f"optwrap_{field}_{safe_oid}"
    with st.container(key=wrapper_key):
        st.button(
            button_label,
            key=f"select_{field}_{safe_oid}",
            disabled=disabled or selected,
            on_click=set_answer,
            args=(field, oid),
            use_container_width=True,
        )


def render_question(step: str, title: str, field: str, options: Iterable[tuple], help_text: str = "", columns_per_row: int = 2):
    ans = current_answers()
    st.markdown('<div class="question-panel compact-question-panel">', unsafe_allow_html=True)
    st.markdown(f'<div class="step-badge">{step}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)
    if help_text:
        st.markdown(f'<div class="section-help">{help_text}</div>', unsafe_allow_html=True)
    options = list(options)
    for i in range(0, len(options), columns_per_row):
        cols = st.columns(columns_per_row, gap="small")
        for col, opt in zip(cols, options[i : i + columns_per_row]):
            with col:
                render_option(field, opt, ans)
    st.markdown("</div>", unsafe_allow_html=True)


def render_slider_question(step: str, title: str, field: str, min_value: int, max_value: int, default: int, help_text: str, suffix: str = " m"):
    ans = current_answers()
    value = int(ans.get(field, default))
    st.markdown('<div class="question-panel compact-question-panel">', unsafe_allow_html=True)
    st.markdown(f'<div class="step-badge">{step}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-help">{help_text}</div>', unsafe_allow_html=True)
    value = st.slider(" ", min_value=min_value, max_value=max_value, value=value, step=1, format=f"%d{suffix}", key=f"slider_{field}", label_visibility="collapsed")
    set_numeric(field, value)
    st.markdown(f'<div class="input-note">Selected: {value}{suffix}</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def render_checkbox_question(step: str, title: str, field: str, help_text: str):
    ans = current_answers()
    st.markdown('<div class="question-panel compact-question-panel">', unsafe_allow_html=True)
    st.markdown(f'<div class="step-badge">{step}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-help">{help_text}</div>', unsafe_allow_html=True)
    val = st.checkbox("Water supply is intermittent or water-scarce", value=bool(ans.get(field)), key="water_scarce_checkbox")
    set_numeric(field, bool(val))
    st.markdown("</div>", unsafe_allow_html=True)


def required_fields(ans: dict) -> list[str]:
    fields = ["setting"]
    if ans.get("setting"):
        fields.append("job")
    if ans.get("job") and ans.get("job") != "drain_sewage":
        fields.append("source")
    if ans.get("job") in {"lift_and_store", "boost_pressure"} and ans.get("source"):
        fields.append("c0_destination")
    if lift_triggered(ans):
        fields.append("lift")
    if ans.get("source") == "borewell":
        fields += ["c1_casing", "c2_depth_m"]
    elif ans.get("source") == "open_well":
        fields.append("c3_depth_m")
    elif ans.get("source") == "open_ground":
        fields.append("c3g_depth_m")
    if ans.get("job") == "drain_sewage":
        fields += ["drain_rate", "c6_quality"]
    elif ans.get("job") in {"lift_and_store", "boost_pressure"}:
        fields.append("demand")
    if ans.get("job") == "boost_pressure":
        fields += ["c4_outlets", "c5_usage", "c5a_pressure"]
    if ans.get("setting") and needs_phase_confirm(ans):
        fields.append("c7_phase")
    if ans.get("setting") and c8_triggered(ans):
        fields.append("c8_duty")
    phase = final_phase(ans)
    if ans.get("setting") and phase:
        if c9_variant(ans["setting"], phase) == "single_band":
            fields.append("c9_voltage_band")
        else:
            fields += ["c9_min_v", "c9_max_v"]
    return list(dict.fromkeys(fields))



def ready_for_power(ans: dict) -> bool:
    """Return True once all non-power hydraulic/path questions are complete."""
    if not ans.get("setting") or not ans.get("job"):
        return False
    if ans.get("job") == "drain_sewage":
        return bool(ans.get("drain_rate") and ans.get("c6_quality"))
    if not ans.get("source") or not ans.get("c0_destination") or not ans.get("demand"):
        return False
    if lift_triggered(ans) and not ans.get("lift"):
        return False
    if ans.get("source") == "borewell" and not (ans.get("c1_casing") and ans.get("c2_depth_m") is not None):
        return False
    if ans.get("source") == "open_well" and ans.get("c3_depth_m") is None:
        return False
    if ans.get("source") == "open_ground" and ans.get("c3g_depth_m") is None:
        return False
    if ans.get("job") == "boost_pressure" and not (ans.get("c4_outlets") and ans.get("c5_usage") and ans.get("c5a_pressure")):
        return False
    return True

def is_complete(ans: dict) -> tuple[bool, list[str]]:
    fields = required_fields(ans)
    return all(ans.get(f) is not None for f in fields), fields


def render_hero(progress_pct: int, sku_count: int):
    st.markdown(
        f"""
        <div class="hero-shell">
          <div class="hero-grid">
            <div>
              <div class="hero-badge">💧 Pump-selection assistant</div>
              <div class="hero-title">Choose a pump from the updated catalogue.</div>
              <p class="hero-copy">
                Answer a short guided questionnaire and get ranked pump recommendations from the current master database.
                This build follows Framework v1.1: matrix-gated paths, conditional lift, metre sliders, the 7 m open-ground-water rule,
                consolidated head, C5a, C7/C8/C9, and corrected voltage containment.
              </p>
            </div>
            <div class="status-card">
              <div class="status-row"><span>Progress</span><span>{progress_pct}%</span></div>
              <div class="progress-rail"><span class="progress-fill" style="width:{progress_pct}%"></span></div>
              <div class="pill-row">
                <span class="ui-pill">{sku_count:,} SKUs loaded</span>
                <span class="ui-pill">v1.1 rules enabled</span>
              </div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_c9(ans: dict):
    phase = final_phase(ans)
    variant = c9_variant(ans["setting"], phase)
    if variant == "single_band":
        render_question("Power detail", "Voltage at pump site", "c9_voltage_band", C9_BAND_OPTIONS, "Home / Shop-office single-phase uses the two-band C9 picker.")
        return

    min_values = allowed_c9_min_values(ans["setting"], phase)
    min_options = [(v, f"{v} V") for v in min_values]
    render_question("Power detail", f"Lowest {'single-phase' if phase == 'Single' else 'three-phase'} voltage", "c9_min_v", min_options, "Enter the lowest sag voltage expected at the pump site.", columns_per_row=4)

    ans = current_answers()
    max_values = allowed_c9_max_values(ans["setting"], phase, ans.get("c9_min_v"))
    max_options = [(v, f"{v} V") for v in max_values]
    render_question("Power detail", f"Highest {'single-phase' if phase == 'Single' else 'three-phase'} voltage", "c9_max_v", max_options, "The Max V dropdown is constrained so it remains greater than Min V.", columns_per_row=4)


def show_soft_warnings(ans: dict):
    for rid, sev, reason in evaluate(ans):
        if sev == "soft":
            st.markdown(f'<div class="warning-box">⚠ Rule #{rid}: {reason}</div>', unsafe_allow_html=True)


def render_vector_panel(vec: dict | None):
    st.markdown('<div class="side-panel">', unsafe_allow_html=True)
    st.markdown('<h2 class="side-title">Requirement vector</h2><p class="side-subtitle">Live hydraulic target used by the matcher.</p>', unsafe_allow_html=True)
    if not vec:
        st.markdown('<div class="empty-card">Complete the questions to build the vector.</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="metric-grid">', unsafe_allow_html=True)
        metrics = [
            ("Pump types", ", ".join(vec["allowed_pump_types"]) or "None", "Matrix whitelist"),
            ("Head", f"{vec['required_min_head']:.0f} / {vec['typical_head']:.0f} m", "Min / typical"),
            ("Flow", f"{vec['required_min_flow']:.0f} / {vec['typical_flow']:.0f} LPH", "Min / typical"),
            ("Phase", vec["final_phase"], "Final C7"),
        ]
        for label, value, sub in metrics:
            st.markdown(f'<div class="metric-card"><small>{label}</small><strong>{value}</strong><span>{sub}</span></div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        with st.expander("Raw vector"):
            st.json(_json_safe(vec))
    st.markdown("</div>", unsafe_allow_html=True)


def _json_safe(v):
    if isinstance(v, set):
        return sorted(v)
    if isinstance(v, dict):
        return {k: _json_safe(val) for k, val in v.items()}
    if isinstance(v, list):
        return [_json_safe(x) for x in v]
    return v

# ---------------------------------------------------------------------------
# Recommendation cards
# ---------------------------------------------------------------------------

NA_STRINGS = {"", "n/a", "na", "nan", "none", "not found", "-", "--", "n.a.", "not available"}


def is_real_value(value) -> bool:
    if value is None:
        return False
    try:
        if pd.isna(value):
            return False
    except Exception:
        pass
    return str(value).strip().lower() not in NA_STRINGS


def clean_value(value):
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def spec_item(label, value):
    if not is_real_value(value):
        return ""
    return f'<div class="spec-box"><div class="spec-label">{label}</div><div class="spec-value">{clean_value(value)}</div></div>'


def spec_range(label, row, min_col, max_col, suffix=""):
    min_v = row.get(min_col)
    max_v = row.get(max_col)
    if not is_real_value(min_v) and not is_real_value(max_v):
        return ""
    if is_real_value(min_v) and is_real_value(max_v):
        value = f"{clean_value(min_v)}–{clean_value(max_v)}{suffix}"
    elif is_real_value(min_v):
        value = f"Min {clean_value(min_v)}{suffix}"
    else:
        value = f"Max {clean_value(max_v)}{suffix}"
    return spec_item(label, value)


def build_spec_summary(row):
    boxes = []
    boxes.append(spec_item("Type", row.get("Type")))
    boxes.append(spec_item("Subtype", row.get("Subtype")))
    boxes.append(spec_item("HP", row.get("HP")))
    boxes.append(spec_item("Phase", row.get("Phase")))
    boxes.append(spec_range("Head range", row, "Min Head (m)", "Max Head (m)", " m"))
    boxes.append(spec_range("Flow range", row, "Min Flow (LPH)", "Max Flow (LPH)", " LPH"))
    boxes.append(spec_item("Pump diameter", row.get("Pump Diameter")))
    boxes.append(spec_range("Single-phase voltage", row, "Single Phase Minimum Voltage", "Single Phase Maximum Voltage", " V"))
    boxes.append(spec_range("Three-phase voltage", row, "Three Phase Minimum Voltage", "Three Phase Maximum Voltage", " V"))
    boxes.append(spec_range("Pressure range", row, "Minimum Pressure (bar)", "Maximum Pressure (bar)", " bar"))
    for label, col, suffix in [
        ("Suction lift", "Suction Lift (m)", " m"),
        ("Speed", "Speed (RPM)", " RPM"),
        ("Tank size", "Tank Size", ""),
        ("Control type", "Control Type", ""),
        ("Cutter type", "Cutter Type", ""),
        ("Cooling type", "Cooling Type", ""),
        ("V3 type", "V3 Type", ""),
        ("Pump size", "Pump Size (mm)", ""),
    ]:
        if col in row.index:
            boxes.append(spec_item(label, f"{clean_value(row.get(col))}{suffix}" if is_real_value(row.get(col)) else row.get(col)))
    return "".join([b for b in boxes if b])


def render_card(rank, row):
    flags = row.get("flags", []) if isinstance(row.get("flags", []), list) else []
    flag_html = "".join(f'<span class="flag-pill">{f}</span>' for f in flags)
    specs_html = build_spec_summary(row)
    st.markdown(
        f"""
        <div class="rec-card detailed-rec-card">
          <div class="rec-top">
            <div>
              <div class="brand-sku"><span class="rank">#{rank}</span>{row.get('Brand', '')} {row.get('SKU', '')}</div>
              <div class="type-line">{row.get('Type', '')}</div>
            </div>
            <div class="score-pill">{int(row.get('score', 0))}</div>
          </div>
          <div class="specs detailed-specs">{specs_html}</div>
          {flag_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def has_borewell_recommendations(scored) -> bool:
    return scored is not None and len(scored) > 0 and "Type" in scored.columns and scored["Type"].astype(str).str.lower().str.contains("borewell", na=False).any()


def render_recommendations(scored, trace=None):
    st.markdown('<div class="side-panel">', unsafe_allow_html=True)
    st.markdown('<h2 class="side-title">Recommendations</h2><p class="side-subtitle">Top matches from the updated master catalogue.</p>', unsafe_allow_html=True)
    if has_borewell_recommendations(scored):
        st.markdown('<div class="warning-pill">If your borewell is prone to sand shedding, consider a compressor pump.</div>', unsafe_allow_html=True)
    if scored is None:
        st.markdown('<div class="empty-card">Recommendations appear after all required answers are complete.</div>', unsafe_allow_html=True)
    elif len(scored) == 0:
        st.markdown('<div class="empty-card">No SKUs survived the current filters. Review head, flow, voltage, or casing constraints.</div>', unsafe_allow_html=True)
    else:
        search = st.text_input("Search recommendations", key="rec_search", placeholder="Brand or SKU")
        view = scored
        if search:
            brand = view["Brand"].astype(str) if "Brand" in view.columns else pd.Series("", index=view.index)
            sku = view["SKU"].astype(str) if "SKU" in view.columns else pd.Series("", index=view.index)
            view = view[brand.str.contains(search, case=False, na=False) | sku.str.contains(search, case=False, na=False)]
        st.markdown(f'<div class="info-box">{len(scored):,} SKUs survived. Showing top 20.</div>', unsafe_allow_html=True)
        for i, (_, row) in enumerate(view.head(20).iterrows(), 1):
            render_card(i, row)
    if trace:
        with st.expander("Filter trace"):
            st.dataframe(pd.DataFrame(trace), use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------


def maybe_render_water_scarcity(ans: dict):
    if ans.get("source") in {"open_ground", "underground_sump", "municipal"}:
        if ans.get("source") != "open_ground" or ans.get("c3g_depth_m", 99) <= 7:
            render_checkbox_question(
                "Optional advisory",
                "Water-scarcity / intermittent supply flag",
                "water_scarce",
                "v1.1 treats Slow-Speed Self-Priming as a ranking advisory, not a hard filter. Use this only when the installation is water-scarce or supply is intermittent.",
            )


def main():
    init_state()
    try:
        catalogue = get_catalogue()
        sku_count = len(catalogue)
    except Exception:
        catalogue = None
        sku_count = 0

    ans = current_answers()
    complete, fields = is_complete(ans)
    answered = sum(1 for f in fields if ans.get(f) is not None)
    progress = int(round(100 * answered / max(1, len(fields))))
    render_hero(progress, sku_count)

    left, right = st.columns([0.62, 0.38], gap="large")
    vec = None
    scored = None
    trace = None

    with left:
        if st.button("Start over", type="secondary"):
            reset_app()
            st.rerun()

        render_question("Step 1", "Where will the pump be used?", "setting", SETTING_OPTIONS, "Setting is asked first because it gates the downstream journey.")
        ans = current_answers()

        if ans.get("setting"):
            render_question("Step 2", "What job should the pump perform?", "job", JOB_OPTIONS, "v1.1 has exactly three jobs.")
            ans = current_answers()

        if ans.get("job") == "drain_sewage":
            st.markdown('<div class="question-panel"><div class="step-badge">Step 3</div><div class="section-title">Source</div><div class="input-note">Drain sewage / water automatically uses Sewage or drainage pit as the source; Destination is not asked.</div></div>', unsafe_allow_html=True)
            set_numeric("source", "sewage_pit")
            set_numeric("c0_destination", None)
            ans = current_answers()
        elif ans.get("job"):
            render_question("Step 3", "What is the water source?", "source", SOURCE_OPTIONS, "The source list is matrix-filtered by Setting + Job.")
            ans = current_answers()

        if ans.get("job") in {"lift_and_store", "boost_pressure"} and ans.get("source"):
            render_question("Step 4", "Where should the water go?", "c0_destination", DEST_OPTIONS, "Destination is matrix-filtered by Setting + Job + Source.")
            ans = current_answers()

        if lift_triggered(ans):
            title = "How high is the overhead tank?" if ans.get("job") == "lift_and_store" else "How high does the water need to go?"
            render_question("Step 5", title, "lift", LIFT_OPTIONS, "Lift appears only when the Job × Destination combination triggers it.")
            ans = current_answers()
        elif ans.get("c0_destination") or ans.get("job") == "drain_sewage":
            if ans.get("job") != "drain_sewage":
                st.markdown('<div class="question-panel"><div class="step-badge">Step 5</div><div class="section-title">Lift</div><div class="input-note">Lift is not triggered for this path, so above-ground lift contributes 0 m.</div></div>', unsafe_allow_html=True)
            ans = current_answers()

        if construction_drain_lift_triggered(ans):
            render_slider_question("Step 5", "Construction-site discharge lift", "construction_lift_m", 0, 80, 0, "Optional for Light-industry drainage. Values up to 3 m are treated as ordinary drainage and contribute 0 m.")
            ans = current_answers()

        if ans.get("source") == "borewell":
            render_question("Source detail", "Borewell casing diameter", "c1_casing", C1_OPTIONS, "C1 filters Borewell candidates by Pump Diameter V-code.")
            render_slider_question("Source detail", "Borewell static rest level", "c2_depth_m", 0, 350, int(ans.get("c2_depth_m", 90)), "C2 is a continuous metre slider. The entered value is added directly to head.")
            ans = current_answers()
        elif ans.get("source") == "open_well":
            render_slider_question("Source detail", "Open-well / pond water depth", "c3_depth_m", 0, 60, int(ans.get("c3_depth_m", 10)), "C3 is a continuous metre slider. The entered value is added directly to head; the type remains Openwell.")
            ans = current_answers()
        elif ans.get("source") == "open_ground":
            render_slider_question("Source detail", "Open-ground-water depth", "c3g_depth_m", 0, 30, int(ans.get("c3g_depth_m", 7)), "C3G applies the 7 m rule: ≤7 m is Self-Priming suction; >7 m is Openwell with depth added to head.")
            ans = current_answers()
            if ans.get("c3g_depth_m") is not None:
                if ans["c3g_depth_m"] <= 7:
                    st.markdown('<div class="info-box">Depth ≤ 7 m: surface Self-Priming family is used, and depth is checked as suction lift rather than added to head.</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="info-box">Depth > 7 m: Self-Priming is excluded; Openwell depth is added to head.</div>', unsafe_allow_html=True)

        if ans.get("job") == "drain_sewage":
            render_question("Step 6", "How much water is to be removed?", "drain_rate", DRAIN_RATE_OPTIONS, "Drain uses a removal-rate table instead of daily demand.")
            render_question("Step 7", "What is the water quality / contents?", "c6_quality", C6_OPTIONS, "C6 sets non-cutter or cutter Sewage pump logic.")
            ans = current_answers()
        elif ans.get("job") in {"lift_and_store", "boost_pressure"} and ans.get("source") and (ans.get("c0_destination") or ans.get("job") == "drain_sewage"):
            render_question("Step 6", "How much water is needed?", "demand", DEMAND_OPTIONS_BY_SETTING.get(ans.get("setting"), []), "The demand table is Setting-specific and maps to an internal representative volume.")
            ans = current_answers()

        if ans.get("job") == "boost_pressure" and ans.get("demand"):
            render_question("Pressure detail", "How many outlets or application points?", "c4_outlets", C4_OPTIONS, "C4 sets the peak outlet flow table.")
            render_question("Pressure detail", "How many will run at the same time?", "c5_usage", C5_OPTIONS, "C5 multiplies the C4 peak flow.")
            render_question("Pressure detail", "Fixture / application pressure class", "c5a_pressure", C5A_BY_SETTING.get(ans.get("setting"), []), "C5a is a head add-on; Home premium fittings can also apply a small-flow floor.")
            ans = current_answers()

        maybe_render_water_scarcity(ans)
        ans = current_answers()

        if ready_for_power(ans):
            if ans.get("setting") and not needs_phase_confirm(ans):
                phase = default_phase(ans["setting"])
                st.markdown(f'<div class="question-panel"><div class="step-badge">Power detail</div><div class="section-title">Power supply phase</div><div class="input-note">Defaulted to {phase}-phase for this Setting.</div></div>', unsafe_allow_html=True)
            elif ans.get("setting"):
                render_question("Power detail", "Power supply phase", "c7_phase", C7_OPTIONS, "C7 is defaulted by Setting, then confirmed where v1.1 requires it.")
                ans = current_answers()

            if ans.get("setting") and c8_triggered(ans):
                render_question("Power detail", "Duty cycle", "c8_duty", C8_OPTIONS, "C8 replaces the demand-table default run-time where triggered.")
                ans = current_answers()

            if ans.get("setting") and final_phase(ans):
                render_c9(ans)
                ans = current_answers()

        complete, fields = is_complete(ans)
        hard_errors = [reason for _rid, sev, reason in evaluate(ans) if sev == "hard"]
        show_soft_warnings(ans)
        for key, msg in lift_flags(ans):
            st.markdown(f'<div class="warning-box">⚠ {msg}</div>', unsafe_allow_html=True)

        if complete and hard_errors:
            for msg in hard_errors:
                st.error(msg)
        elif complete and catalogue is not None:
            vec = build_vector(ans)
            survivors, trace = filter_skus(catalogue, vec)
            scored = score_skus(survivors, vec)
        elif complete and catalogue is None:
            st.error("Catalogue file was not found or could not be loaded.")

        if not complete:
            missing = [f for f in fields if ans.get(f) is None]
            if missing:
                st.markdown(f'<div class="info-box">Waiting for: {", ".join(missing)}</div>', unsafe_allow_html=True)

    with right:
        st.markdown('<div class="side-stack">', unsafe_allow_html=True)
        render_vector_panel(vec)
        render_recommendations(scored, trace)
        st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
