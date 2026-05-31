"""Streamlit Pump Selection Assistant aligned to Framework v1.2."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

import pandas as pd
import streamlit as st

from rules import evaluate
from scoring import filter_skus, lift_flags, score_skus
from vector import (
    DRAIN_QUANTITY_RANGE_BY_SETTING,
    DRAIN_TIME_HOUR_STOPS,
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
    final_phase,
    lift_triggered,
    needs_phase_confirm,
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
.requirement-card { border:1px solid var(--line,#e2e8f0); background:#fff; border-radius:18px; padding:14px; margin:10px 0; }
.requirement-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; margin-top:12px; }
.requirement-cell { border:1px solid var(--line,#e2e8f0); background:#f8fafc; border-radius:16px; padding:12px; }
.requirement-cell small { display:block; color:#64748b; font-weight:800; margin-bottom:5px; }
.requirement-cell strong { color:#0f172a; font-size:1rem; line-height:1.25; }
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

DRAIN_QUANTITY_STOPS = [100, 250, 500, 1000, 2000, 5000, 10000, 25000, 50000, 100000, 250000, 500000]
DRAIN_TIME_STOPS = DRAIN_TIME_HOUR_STOPS

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

FARM_C4_OPTIONS_BY_C5A = {
    "farm_flood": [
        ("farm_flood_1_2", "1–2 field outlets / furrow channels"),
        ("farm_flood_3_5", "3–5 field outlets / furrow channels"),
        ("farm_flood_6_10", "6–10 field outlets / furrow channels"),
        ("farm_flood_above_10", "More than 10 field outlets / furrow channels"),
    ],
    "farm_drip": [
        ("farm_drip_1_3", "1–3 drip zones / trough points"),
        ("farm_drip_4_8", "4–8 drip zones / trough points"),
        ("farm_drip_9_18", "9–18 drip zones / trough points"),
        ("farm_drip_above_18", "More than 18 drip zones / trough points"),
    ],
    "farm_sprinkler": [
        ("farm_sprinkler_1_4", "1–4 sprinkler heads / wash-down points"),
        ("farm_sprinkler_5_12", "5–12 sprinkler heads / wash-down points"),
        ("farm_sprinkler_13_25", "13–25 sprinkler heads / wash-down points"),
        ("farm_sprinkler_26_50", "26–50 sprinkler heads / wash-down points"),
        ("farm_sprinkler_above_50", "More than 50 sprinkler heads / wash-down points"),
    ],
    "farm_rain_gun": [
        ("farm_rain_gun_1", "1 rain gun / high-pressure sprinkler"),
        ("farm_rain_gun_2_3", "2–3 rain guns / high-pressure sprinklers"),
        ("farm_rain_gun_4_6", "4–6 rain guns / high-pressure sprinklers"),
        ("farm_rain_gun_above_6", "More than 6 rain guns / high-pressure sprinklers"),
    ],
}

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
        "farm": "Irrigation, crop watering, livestock, or agricultural property.",
        "shop_small_comm": "Showrooms, small offices, clinics, restaurants, or small retail spaces.",
        "large_commercial": "Hotels, hospitals, schools, hostels, apartment blocks, colleges, or similar properties.",
        "light_industry": "Factories, warehouses, construction projects, or light-manufacturing sites.",
    },
    "job": {
        "lift_and_store": "Fill an overhead tank or a ground-level storage tank / sump for later use.",
        "boost_pressure": "Improve water pressure for building pipes, irrigation / livestock lines, or an industrial process.",
        "drain_sewage": "Empty a sewage, drainage, storm-water, or waste-water pit.",
    },
    "source": {
        "borewell": "A deep underground source with a narrow casing pipe.",
        "open_well": "An open water body or well that is accessible from the top.",
        "open_ground": "A canal, river, farm channel, or similar surface-water source.",
        "underground_sump": "A ground-level or below-ground tank that already holds water.",
        "overhead_tank": "A tank that is already placed at height.",
        "municipal": "An external piped or shared-society water line used to fill a storage tank.",
        "sewage_pit": "A collection pit for drain water, grey water, storm water, sewage, or waste water.",
    },
    "c0_destination": {
        "overhead_tank": "Store water above ground for later use.",
        "ground_sump": "Store water at ground level or below ground for later use.",
        "direct_pipes": "Send pressurised water directly to building plumbing.",
        "irrigation": "Supply water to farm lines, open fields, or livestock areas.",
        "industrial_process": "Supply water to a process line, treatment system, wash-down point, or production area.",
    },
    "c1_casing": {
        "casing_4in": "Common narrow bore casing for smaller borewell pumps.",
        "casing_6in": "A common borewell casing size for home, farm, and commercial installations.",
        "casing_8in": "A wider borewell casing often used for larger-capacity pumps.",
        "casing_10in": "A large borewell casing for higher-capacity installations.",
        "casing_12in_plus": "Very large borewell casing for special or high-capacity installations.",
    },
    "c4_outlets": {
        "1_4": "A small fixture set, such as a compact home or a few taps.",
        "5_12": "A small home, compact office, shop, or similar fixture set.",
        "13_20": "A large home, small commercial space, or several application points.",
        "21_35": "Hotel floor, clinic, farm shed, small institution, or similar peak use.",
        "36_75": "Mid-size hotel, hostel, dairy, office floor, or larger service area.",
        "76_150": "Large hotel, apartment block, institution, or farm application.",
        "above_150": "Large complex, campus, estate, or industrial site.",
        "farm_flood_1_2": "Small field channel or hand-watering setup.",
        "farm_flood_3_5": "Several furrows or field outlets operating from one pump.",
        "farm_flood_6_10": "Larger field section with many channels.",
        "farm_flood_above_10": "Large flood/furrow layout; confirm pipe sizing.",
        "farm_drip_1_3": "Small drip or livestock group.",
        "farm_drip_4_8": "Moderate drip zoning or trough distribution.",
        "farm_drip_9_18": "Large drip or livestock network.",
        "farm_drip_above_18": "Very large drip zoning; confirm irrigation design.",
        "farm_sprinkler_1_4": "Small sprinkler block or wash-down area.",
        "farm_sprinkler_5_12": "Typical farm sprinkler group.",
        "farm_sprinkler_13_25": "Larger sprinkler block.",
        "farm_sprinkler_26_50": "Large sprinkler network; confirm pipe sizing.",
        "farm_sprinkler_above_50": "Very large sprinkler network; likely needs design review.",
        "farm_rain_gun_1": "Single high-pressure rain-gun point.",
        "farm_rain_gun_2_3": "Small high-pressure rain-gun group.",
        "farm_rain_gun_4_6": "Larger high-pressure rain-gun group.",
        "farm_rain_gun_above_6": "Very large rain-gun layout; likely needs design review.",
    },
    "c5_usage": {
        "light": "Most outlets are used one at a time. Typical for a small home.",
        "moderate": "About half the outlets may run together. Typical for a family home or small office at peak times.",
        "heavy": "Many outlets may run together. Typical for commercial peaks or morning rush.",
        "constant_peak": "Most or all outlets may run together. Typical for wash-down or demanding site use.",
    },
    "c5a_pressure": {
        "home_standard": "Regular taps, showers, and household fittings.",
        "home_premium": "Rain showers, body jets, or large overhead showers.",
        "shop_standard": "Regular shop, office, clinic, or pantry fixtures.",
        "shop_premium": "Salon, spa, boutique-hotel shower, or similar premium fixtures.",
        "large_comm_standard": "Regular washroom and service fixtures.",
        "large_comm_premium": "Premium guest-room, spa, pool-deck, or higher-comfort fittings.",
        "farm_flood": "Flood, furrow, or hand-watering only.",
        "farm_drip": "Drip irrigation or livestock troughs.",
        "farm_sprinkler": "Sprinklers or general farm wash-down.",
        "farm_rain_gun": "Rain guns or high-pressure sprinklers.",
        "industry_standard": "Standard washroom and canteen use only.",
        "industry_light_wash": "Light wash-down for a small factory or warehouse.",
        "industry_routine_wash": "Routine production washing.",
        "industry_heavy_jetting": "Heavy wash-down or high-pressure jetting.",
    },
    "c6_quality": {
        "clean_water": "Clear water from a pit, basement, or collection sump.",
        "lightly_soiled": "Grey water or lightly dirty water from washing, bathrooms, or general drainage.",
        "solids_waste": "Waste water that may contain solids or debris.",
        "heavy_sewage": "Heavy sewage or waste water with a high solids load.",
    },
    "c7_phase": {
        "Single": "Standard home-style supply.",
        "Three": "Common for farms, factories, and larger commercial sites.",
    },
    "c8_duty": {
        "moderate": "Used for a few hours a day, such as a large home, small commercial site, or small farm.",
        "heavy": "Runs for a long daily shift, such as a hotel, mid-size farm, or factory.",
        "continuous": "Runs for most of the day, such as an industrial process, high-rise system, or large agriculture use.",
    },
    "c9_voltage_band": {
        LOW_C9_BAND: "Choose this if supply often drops below 200 V.",
        NORMAL_C9_BAND: "Choose this for a typical 200–240 V supply.",
    },
}

FIELD_ORDER = [
    "setting", "job", "source", "c0_destination", "lift", "construction_lift_m",
    "c1_casing", "c2_depth_m", "c3_depth_m", "c3g_depth_m", "demand", "drain_quantity_l", "drain_time_h",
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
    if field == "c5a_pressure" and ans.get("setting") == "farm" and previous != value:
        ans.pop("c4_outlets", None)
        ans.pop("c5_usage", None)
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
    if field in {"c9_min_v", "c9_max_v"}:
        return "Choose the nearest value you normally see at the pump location."
    return OPTION_DESCRIPTIONS.get(field, {}).get(option_id, "")


DEMAND_DESCRIPTIONS_BY_SETTING = {
    "home": {
        "vol_200": "Single-person flat or studio, about 1 bathroom, minimal kitchen use.",
        "vol_800": "Small family, 1 bathroom, 1-BHK or compact 2-BHK, regular kitchen and laundry.",
        "vol_2000": "Nuclear or joint family, 2–4 bathrooms, 3–4 BHK flat or villa, possibly a small garden.",
        "vol_5000": "Large independent home or small farmhouse with 5+ bathrooms, garden, car-wash, occasional pool top-up, or staff quarters.",
    },
    "farm": {
        "vol_800": "Homestead / farmhouse domestic use only, a few animals, or a hand-watered kitchen garden under ~200 sq ft.",
        "vol_2000": "Larger homestead or backyard livestock only, troughs, animal washing, or kitchen garden under ~500 sq ft.",
        "vol_10000": "Very small irrigated plot or small dairy; drip up to ~⅓ acre, sprinkler up to ~¼ acre.",
        "vol_50000": "Small-to-mid irrigated farm; drip ~⅓–1.5 acres, sprinkler ~¼–1 acre, or livestock-only use.",
        "vol_200000": "Mid-to-large commercial farm; drip ~1.5–6 acres, sprinkler ~1–5 acres, or larger livestock use.",
        "vol_above_200000": "Large commercial farm, estate, or plantation with 6+ acres drip, 5+ acres sprinkler, or large livestock use.",
    },
    "shop_small_comm": {
        "vol_200": "Kiosk or single-staff outlet with 1–2 staff and one shared washroom.",
        "vol_800": "Small shop or compact office with 3–15 staff, 1–2 washrooms, and a basic pantry.",
        "vol_2000": "Mid-size office, clinic, or retail site with 15–40 staff, 2–4 washrooms, and a small pantry.",
        "vol_5000": "Large office floor or small restaurant with 40–100 staff, canteen, 30–50 seats, or standalone clinic use.",
        "vol_10000": "Large standalone commercial premises, mid-size restaurant, small guesthouse, or small banquet hall.",
    },
    "large_commercial": {
        "vol_5000": "Very small institutional site, such as 4–9 flats, 5–10 budget rooms, or a small school/day facility.",
        "vol_10000": "Small institutional site, such as 9–18 flats, 10–20 rooms, small hostel, or 10–20 bed hospital.",
        "vol_50000": "Mid-size institutional site, such as 18–90 flats, 30–100 hotel rooms, school, hostel, or 25–100 bed hospital.",
        "vol_200000": "Large institutional site, such as 90–370 flats, large hotel, major school/college, or 100–400 bed hospital.",
        "vol_above_200000": "Very large institutional site, township, large campus, 500+ room hotel, or 400+ bed hospital.",
    },
    "light_industry": {
        "vol_800": "Small workshop or storage shed with 5–15 workers, one washroom, and minimal process water.",
        "vol_2000": "Small factory or warehouse with 15–40 workers, 2 washrooms, basic canteen, or occasional floor washing.",
        "vol_5000": "Mid-size factory or active site with 40–100 workers, daily wash-down, or light process water.",
        "vol_10000": "Large factory or major construction with 100–200 workers and significant wash-down or process water.",
        "vol_50000": "Mid-size industrial unit with active production, cooling, washing, batching, or a major construction project.",
        "vol_200000": "Large industrial unit with 800+ workers or continuous-flow process use.",
        "vol_above_200000": "Industrial estate, very large factory, infrastructure project, or special-purpose site.",
    },
}

DRAIN_QUANTITY_DESCRIPTIONS = {
    100: "Small sump pit or bathroom wastewater",
    250: "Large pit or small collection chamber",
    500: "Small tank or accumulated drainage water",
    1000: "One kilolitre tank or storage chamber",
    2000: "Small underground tank or holding tank",
    5000: "Large storage tank or basement water removal",
    10000: "Large tank, flooded basement, or site drainage",
    25000: "Major water accumulation or commercial drainage",
    50000: "Heavy drainage, floodwater, or large site dewatering",
    100000: "Large-scale site dewatering or multi-block drainage",
    250000: "Major infrastructure or continuous dewatering",
    500000: "Very large dewatering; usually a multi-pump scheme",
}

DRAIN_TIME_DESCRIPTIONS = {
    0.25: "Clear it almost immediately — urgent / flooding.",
    0.5: "Clear it quickly.",
    0.75: "Clear it fairly quickly.",
    1: "Clear it within the hour.",
    2: "Steady clearing over a couple of hours.",
    4: "Gradual clearing over a half-day.",
    6: "Slow clearing across a working shift.",
    8: "Slowest setting — clear it over a full shift.",
}


def demand_description(setting: str | None, option_id: str) -> str:
    return DEMAND_DESCRIPTIONS_BY_SETTING.get(setting or "", {}).get(option_id, "")



def disabled_reason_for_candidate(field: str, candidate_value, ans: dict):
    if field == "job" and ans.get("setting"):
        if candidate_value not in available_jobs(ans["setting"]):
            return "This job type is not available for the selected site."

    if field == "source" and ans.get("setting") and ans.get("job"):
        if candidate_value not in available_sources(ans["setting"], ans["job"]):
            job = ans.get("job")
            setting = ans.get("setting")
            if candidate_value == "sewage_pit":
                return "Choose this only when the job is to drain or empty a pit."
            if candidate_value == "overhead_tank":
                return "An overhead tank can be used as a source only when boosting pressure to building pipes."
            if candidate_value == "municipal":
                if job == "boost_pressure":
                    return "Shared piped supply is supported for filling a ground-level tank, not for direct pressure boosting."
                return "Shared piped supply is only used where the water is going into a ground-level tank or sump."
            if candidate_value == "open_ground":
                if setting == "home":
                    return "Canals, rivers, and farm channels are not a home water-source option."
                return "Open surface water is available only for farm use and selected ground-level transfer cases."
            if candidate_value == "open_well":
                return "Open wells are offered only where the site type and job commonly use an openwell pump."
            if candidate_value == "borewell":
                return "Borewell use is available only where the water is being lifted from the bore or used for farm / process delivery."
            if candidate_value == "underground_sump":
                return "A sump or storage tank is available only when stored water is part of the selected use case."
            return "This source does not match the selected site and pump job."

    if field == "c0_destination" and ans.get("setting") and ans.get("job") and ans.get("source"):
        if candidate_value not in available_destinations(ans["setting"], ans["job"], ans["source"]):
            job = ans.get("job")
            source = ans.get("source")
            setting = ans.get("setting")
            if candidate_value == "overhead_tank":
                if job == "boost_pressure":
                    return "For pressure boosting, the tank is the water source, not the destination."
                if source == "municipal":
                    return "Shared piped supply is supported for filling a ground-level tank or sump."
                if source == "open_ground" and setting == "shop_small_comm":
                    return "For this site type, open surface water is available only for ground-level storage."
                return "This source is not suitable for filling an overhead tank on the selected site."
            if candidate_value == "ground_sump":
                if job == "boost_pressure":
                    return "Ground-level storage is a storage-fill destination, not a pressure-delivery point."
                return "This source is available only for overhead-tank fill on the selected site."
            if candidate_value == "direct_pipes":
                if job == "lift_and_store":
                    return "Direct building pipes are for pressure boosting, not storage fill."
                if source in {"borewell", "open_well", "open_ground"}:
                    return "This source is not used for direct building pressure in the selected site type."
                return "Direct building pressure is available only from a suitable tank source."
            if candidate_value == "irrigation":
                return "Irrigation and livestock lines are available for farm pressure applications."
            if candidate_value == "industrial_process":
                return "Industrial process delivery is available for larger commercial or light-industrial sites."
            return "This destination does not match the selected source and job."

    if field == "c9_max_v" and ans.get("c9_min_v") is not None:
        if candidate_value <= ans["c9_min_v"]:
            return "Choose a value higher than the lowest voltage."
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


def floor_example_text(floors: int) -> str:
    if floors <= 0:
        return "Same level or ground-floor-only use."
    if floors == 1:
        return "Ground plus one floor, such as a first-floor tank or low-rise delivery point."
    if floors == 2:
        return "Small home or low-rise building with water needed up to the second floor."
    if floors == 3:
        return "Independent house, low-rise commercial space, or third-floor delivery point."
    if floors == 4:
        return "Top of a typical independent house or similar low-rise site."
    if floors <= 10:
        return "Low-rise apartment, hostel, or small commercial building."
    if floors <= 15:
        return "Mid-rise building where a stronger pumping arrangement is usually needed."
    if floors <= 25:
        return "High-rise building; staged pumping is usually preferred in practice."
    if floors <= 40:
        return "Tall building; a multi-zone pressure arrangement is typically used."
    return "Very tall building; consultant review is recommended before final selection."


def depth_example_text(field: str, value: int) -> str:
    if field == "c2_depth_m":
        if value < 15:
            return "Water level close to ground level; common in high-water-table areas."
        if value < 30:
            return "Shallow borewell, common for many domestic sites."
        if value < 60:
            return "Typical domestic borewell water level."
        if value < 90:
            return "Deeper domestic borewell, often seen in drier areas."
        if value < 135:
            return "Low-water-table borewell, common in deeper domestic or farm use."
        if value < 180:
            return "High-depth borewell often used for farm or large-property supply."
        if value < 245:
            return "High-depth agricultural or large-property borewell."
        if value < 305:
            return "Very deep borewell, usually agricultural or institutional."
        return "Special-case deep borewell, usually for industrial, large agricultural, or site-specific use."

    if field == "c3_depth_m":
        if value < 2:
            return "Water level very close to ground level; common in wet-season or recharge-zone conditions."
        if value < 3:
            return "Shallow open well where groundwater is easily accessible."
        if value < 6:
            return "Moderately shallow open well, typical for stable groundwater zones."
        if value < 9:
            return "Moderate-depth open well; may reflect seasonal variation or lower recharge."
        if value < 15:
            return "Deeper open well, common in drier regions or lower-water-table areas."
        if value < 21:
            return "Very deep open well, often associated with dry or heavily extracted zones."
        if value < 30:
            return "Unusually deep open well; site access and lining should be checked carefully."
        return "Special-case open well; confirm site conditions before final selection."

    if field == "c3g_depth_m":
        if value <= 3:
            return "Very shallow canal, river, or channel draw-off. A surface setup is usually practical."
        if value <= 7:
            return "Shallow surface-water draw-off within the usual suction range."
        if value <= 12:
            return "Deeper surface water; a pump placed in the water is usually more practical."
        return "Deep surface-water draw-off; confirm access and installation method before final selection."

    if field == "construction_lift_m":
        if value <= 3:
            return "Minor lift, such as ordinary pit drainage or floor-level dewatering."
        if value <= 10:
            return "Small construction-site discharge lift."
        if value <= 30:
            return "Moderate construction-site discharge lift."
        return "High discharge lift; site review is recommended before final selection."

    return ""


def render_slider_question(step: str, title: str, field: str, min_value: int, max_value: int, default: int, help_text: str = "", suffix: str = " m"):
    ans = current_answers()
    value = int(ans.get(field, default))
    value = max(min_value, min(max_value, value))
    st.markdown('<div class="question-panel compact-question-panel">', unsafe_allow_html=True)
    st.markdown(f'<div class="step-badge">{step}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)
    if help_text:
        st.markdown(f'<div class="section-help">{help_text}</div>', unsafe_allow_html=True)
    value = st.slider(" ", min_value=min_value, max_value=max_value, value=value, step=1, format=f"%d{suffix}", key=f"slider_{field}", label_visibility="collapsed")
    set_numeric(field, value)
    example = depth_example_text(field, int(value))
    if example:
        st.markdown(f'<div class="input-note">{example}</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


LIFT_MAX_FLOORS_BY_SETTING = {
    "home": 5,
    "shop_small_comm": 5,
    "farm": 3,
    "large_commercial": 60,
    "light_industry": 40,
}


def render_floor_slider_question(step: str, title: str, field: str = "lift", default: int = 0):
    ans = current_answers()
    raw_value = ans.get(field, default)
    legacy_floor_values = {
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
    max_floors = LIFT_MAX_FLOORS_BY_SETTING.get(ans.get("setting"), 60)
    try:
        value = int(raw_value)
    except Exception:
        value = legacy_floor_values.get(str(raw_value), default)
    value = max(0, min(max_floors, value))
    st.markdown('<div class="question-panel compact-question-panel">', unsafe_allow_html=True)
    st.markdown(f'<div class="step-badge">{step}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-help">Move the slider to the highest floor or tank level the water needs to reach. This setting allows up to {max_floors} floor(s).</div>', unsafe_allow_html=True)
    value = st.slider(" ", min_value=0, max_value=max_floors, value=value, step=1, format="%d floor(s)", key=f"slider_{field}", label_visibility="collapsed")
    set_numeric(field, int(value))
    suffix = f" Estimated vertical lift: {int(value) * 3} m." if ans.get("setting") == "farm" else ""
    st.markdown(f'<div class="input-note">{floor_example_text(int(value))}{suffix}</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def _format_litres(value: int) -> str:
    return f"{value:,} L"


def _format_hours(value: float) -> str:
    if value == 0.25:
        return "15 min"
    if value == 0.5:
        return "30 min"
    if value == 0.75:
        return "45 min"
    return f"{int(value)} hr" if float(value).is_integer() else f"{value:g} hr"


def render_select_slider_question(step: str, title: str, field: str, options: list, default, help_text: str, format_func, description_lookup: dict):
    ans = current_answers()
    value = ans.get(field, default)
    if value not in options:
        value = default if default in options else options[0]
    st.markdown('<div class="question-panel compact-question-panel">', unsafe_allow_html=True)
    st.markdown(f'<div class="step-badge">{step}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-help">{help_text}</div>', unsafe_allow_html=True)
    value = st.select_slider(" ", options=options, value=value, format_func=format_func, key=f"slider_{field}", label_visibility="collapsed")
    set_numeric(field, value)
    desc = description_lookup.get(value, "")
    if desc:
        st.markdown(f'<div class="input-note">{desc}</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def render_drain_quantity_slider(ans: dict):
    mn, mx = DRAIN_QUANTITY_RANGE_BY_SETTING.get(ans.get("setting"), (100, 50000))
    options = [v for v in DRAIN_QUANTITY_STOPS if mn <= v <= mx]
    default = options[min(3, len(options) - 1)]
    render_select_slider_question(
        "Step 6",
        "How much water or sewage needs to be pumped out?",
        "drain_quantity_l",
        options,
        default,
        "Choose the closest quantity to be cleared from the pit, sump, basement, or site.",
        _format_litres,
        DRAIN_QUANTITY_DESCRIPTIONS,
    )


def render_drain_time_slider():
    render_select_slider_question(
        "Step 7",
        "In how much time should it be pumped out?",
        "drain_time_h",
        DRAIN_TIME_STOPS,
        1,
        "Shorter times need a higher-flow pump; longer times allow a smaller flow requirement.",
        _format_hours,
        DRAIN_TIME_DESCRIPTIONS,
    )


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
        fields += ["drain_quantity_l", "drain_time_h", "c6_quality"]
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
        return bool(ans.get("drain_quantity_l") and ans.get("drain_time_h") and ans.get("c6_quality"))
    if not ans.get("source") or not ans.get("c0_destination") or not ans.get("demand"):
        return False
    if lift_triggered(ans) and ans.get("lift") is None:
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
                Answer a short guided questionnaire and get ranked pump recommendations from the current product catalogue.
                We’ll only ask questions that are relevant to your site and water use.
              </p>
            </div>
            <div class="status-card">
              <div class="status-row"><span>Progress</span><span>{progress_pct}%</span></div>
              <div class="progress-rail"><span class="progress-fill" style="width:{progress_pct}%"></span></div>
              <div class="pill-row">
                <span class="ui-pill">{sku_count:,} products in catalogue</span>
                <span class="ui-pill">Guided selection</span>
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
        render_question("Power detail", "Voltage at pump site", "c9_voltage_band", C9_BAND_OPTIONS, "Choose the voltage condition that best matches your site.")
        return

    min_values = allowed_c9_min_values(ans["setting"], phase)
    min_options = [(v, f"{v} V") for v in min_values]
    render_question("Power detail", f"Lowest {'single-phase' if phase == 'Single' else 'three-phase'} voltage", "c9_min_v", min_options, "Choose the lowest voltage you normally see at the pump location.", columns_per_row=4)

    ans = current_answers()
    max_values = allowed_c9_max_values(ans["setting"], phase, ans.get("c9_min_v"))
    max_options = [(v, f"{v} V") for v in max_values]
    render_question("Power detail", f"Highest {'single-phase' if phase == 'Single' else 'three-phase'} voltage", "c9_max_v", max_options, "Choose the highest voltage you normally see at the pump location.", columns_per_row=4)


def show_soft_warnings(ans: dict):
    for _rid, sev, reason in evaluate(ans):
        if sev == "soft":
            st.markdown(f'<div class="warning-box">⚠ {reason}</div>', unsafe_allow_html=True)


def _fmt_number(value, suffix=""):
    try:
        number = float(value)
    except Exception:
        return "—"
    if number >= 1000 and suffix.strip().upper() == "LPH":
        return f"{number:,.0f} {suffix}".strip()
    if number.is_integer():
        return f"{int(number):,} {suffix}".strip()
    return f"{number:,.1f} {suffix}".strip()


def render_requirement_matrix(vec: dict):
    if not vec:
        return
    phase = vec.get("final_phase") or "—"
    pump_types = ", ".join(vec.get("allowed_pump_types") or []) or "—"
    friendly = [
        ("Lift / pressure", f"About {_fmt_number(vec.get('typical_head'), 'm')} target head"),
        ("Delivery", f"About {_fmt_number(vec.get('typical_flow'), 'LPH')} target flow"),
        ("Power", f"{phase}-phase" if phase != "—" else "—"),
        ("Suitable pump type(s)", pump_types),
    ]
    st.markdown('<div class="requirement-card">', unsafe_allow_html=True)
    st.markdown('<h3 class="section-title">Requirement matrix</h3><p class="section-help">Shown before SKUs so the sizing assumptions are visible.</p>', unsafe_allow_html=True)
    st.markdown('<div class="requirement-grid">', unsafe_allow_html=True)
    for label, value in friendly:
        st.markdown(f'<div class="requirement-cell"><small>{label}</small><strong>{value}</strong></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    special = vec.get("special", {})
    if special.get("c9_variant") == "single_band":
        voltage = "Single-phase band: below 200 V" if special.get("c9_band") == LOW_C9_BAND else "Single-phase band: 200–240 V"
    elif special.get("c9_variant") in {"farm_single_range", "three_phase_range"}:
        voltage = f"{special.get('c9_min_v', '—')}–{special.get('c9_max_v', '—')} V site range"
    else:
        voltage = "—"
    hp_cap = vec.get("hp_cap")
    hp_cap_text = f"Preferred {hp_cap} HP; hard cap {2 * hp_cap} HP" if hp_cap else "No setting cap"
    rows = [
        ["Eligible pump type(s)", pump_types, "SKU Type must be in this set."],
        ["Required minimum head", _fmt_number(vec.get("required_min_head"), "m"), "Keep SKUs with Max Head at or above this hard floor."],
        ["Head upper-edge target", _fmt_number(vec.get("typical_head"), "m"), "Keep SKUs with Min Head at or below this target; also used for ranking."],
        ["Required minimum flow", _fmt_number(vec.get("required_min_flow"), "LPH"), "Keep SKUs with Max Flow at or above this hard floor."],
        ["Flow upper-edge target", _fmt_number(vec.get("typical_flow"), "LPH"), "Keep SKUs with Min Flow at or below this target; also used for ranking."],
        ["Power supply phase", f"{phase}-phase" if phase != "—" else "—", "Keep Single/Both or Three/Both according to the final phase."],
        ["Voltage envelope", voltage, "Apply the C9 voltage hard filter and ranking headroom."],
        ["HP cap", hp_cap_text, "Apply the Home / Shop hard cap and soft oversize penalty where relevant."],
    ]
    with st.expander("Sales-engineer view"):
        st.table(pd.DataFrame(rows, columns=["Specification", "Value", "How it filters / ranks"]))
    st.markdown('</div>', unsafe_allow_html=True)


def render_vector_panel(vec: dict | None):
    ans = current_answers()
    st.markdown('<div class="side-panel">', unsafe_allow_html=True)
    st.markdown('<h2 class="side-title">Selection summary</h2><p class="side-subtitle">Your answers will guide the recommendations.</p>', unsafe_allow_html=True)
    if not vec:
        st.markdown('<div class="empty-card">Complete the questions to see the requirement matrix and matched pump recommendations.</div>', unsafe_allow_html=True)
    else:
        summary_items = []
        if ans.get("source"):
            summary_items.append(("Water source", SOURCES.get(ans.get("source"), ans.get("source"))))
        if ans.get("c0_destination"):
            summary_items.append(("Water goes to", dict(DEST_OPTIONS).get(ans.get("c0_destination"), ans.get("c0_destination"))))
        if ans.get("demand"):
            label = dict(DEMAND_OPTIONS_BY_SETTING.get(ans.get("setting"), [])).get(ans.get("demand"), "Selected demand")
            summary_items.append(("Water use", label))
        if ans.get("drain_quantity_l"):
            summary_items.append(("Drainage volume", _format_litres(int(ans.get("drain_quantity_l")))))
        if ans.get("drain_time_h"):
            summary_items.append(("Clear-out time", _format_hours(float(ans.get("drain_time_h")))))
        if final_phase(ans):
            summary_items.append(("Power", f"{final_phase(ans)}-phase"))
        st.markdown('<div class="metric-grid">', unsafe_allow_html=True)
        for label, value in summary_items[:4]:
            st.markdown(f'<div class="metric-card"><small>{label}</small><strong>{value}</strong></div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        render_requirement_matrix(vec)
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
    st.markdown('<h2 class="side-title">Recommendations</h2><p class="side-subtitle">Top product matches for your answers.</p>', unsafe_allow_html=True)
    if has_borewell_recommendations(scored):
        st.markdown('<div class="warning-pill">If your borewell is prone to sand shedding, consider a compressor pump.</div>', unsafe_allow_html=True)
    if scored is None:
        st.markdown('<div class="empty-card">Recommendations appear after all required answers are complete.</div>', unsafe_allow_html=True)
    elif len(scored) == 0:
        st.markdown('<div class="empty-card">No products matched this combination. Try reviewing the site height, water amount, voltage, or borewell casing size.</div>', unsafe_allow_html=True)
    else:
        search = st.text_input("Search recommendations", key="rec_search", placeholder="Brand or model")
        view = scored
        if search:
            brand = view["Brand"].astype(str) if "Brand" in view.columns else pd.Series("", index=view.index)
            sku = view["SKU"].astype(str) if "SKU" in view.columns else pd.Series("", index=view.index)
            view = view[brand.str.contains(search, case=False, na=False) | sku.str.contains(search, case=False, na=False)]
        st.markdown(f'<div class="info-box">Showing the top matches from {len(scored):,} suitable products.</div>', unsafe_allow_html=True)
        for i, (_, row) in enumerate(view.head(20).iterrows(), 1):
            render_card(i, row)
    st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------


def path_allows_self_priming(ans: dict) -> bool:
    if ans.get("job") == "drain_sewage":
        return False
    key = (ans.get("setting"), ans.get("job"), ans.get("source"), ans.get("c0_destination"))
    if None in key:
        return False
    allowed = MATRIX.get(key, [])
    if "Self-Priming Pump" not in allowed:
        return False
    if ans.get("source") == "open_ground" and float(ans.get("c3g_depth_m") or 99) > 7:
        return False
    return True


def maybe_render_water_scarcity(ans: dict):
    if path_allows_self_priming(ans):
        render_checkbox_question(
            "Optional advisory",
            "Water supply condition",
            "water_scarce",
            "Select this only when a Self-Priming option is eligible and the source is intermittent, slow to refill, or water-scarce.",
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

        render_question("Step 1", "Where will the pump be used?", "setting", SETTING_OPTIONS, "Choose the place that best matches the installation site.")
        ans = current_answers()

        if ans.get("setting"):
            render_question("Step 2", "What job should the pump perform?", "job", JOB_OPTIONS, "Choose what you need the pump to do.")
            ans = current_answers()

        if ans.get("job") == "drain_sewage":
            set_numeric("source", "sewage_pit")
            set_numeric("c0_destination", None)
            ans = current_answers()
        elif ans.get("job"):
            render_question("Step 3", "What is the water source?", "source", SOURCE_OPTIONS, "Choose where the water is coming from.")
            ans = current_answers()

        if ans.get("job") in {"lift_and_store", "boost_pressure"} and ans.get("source"):
            render_question("Step 4", "Where should the water go?", "c0_destination", DEST_OPTIONS, "Choose where the pump should deliver the water.")
            ans = current_answers()

        if lift_triggered(ans):
            title = "How many floors up is the overhead tank?" if ans.get("job") == "lift_and_store" else "How many floors up does the water need to reach?"
            render_floor_slider_question("Step 5", title)
            ans = current_answers()

        if construction_drain_lift_triggered(ans):
            render_slider_question("Step 5", "Construction-site discharge lift", "construction_lift_m", 0, 80, 0, "Use this when drainage water must be discharged to a noticeably higher point.")
            ans = current_answers()

        if ans.get("source") == "borewell":
            render_question("Source detail", "Borewell casing diameter", "c1_casing", C1_OPTIONS, "Choose the borewell casing size at the installation site.")
            render_slider_question("Source detail", "Borewell static rest level", "c2_depth_m", 0, 350, int(ans.get("c2_depth_m", 90)), "Move the slider to the approximate resting water level in the borewell.")
            ans = current_answers()
        elif ans.get("source") == "open_well":
            render_slider_question("Source detail", "Open-well / pond water depth", "c3_depth_m", 0, 40, int(ans.get("c3_depth_m", 10)), "Move the slider to the approximate water depth in the open well or pond.")
            ans = current_answers()
        elif ans.get("source") == "open_ground":
            render_slider_question("Source detail", "Open-ground-water depth", "c3g_depth_m", 0, 20, int(ans.get("c3g_depth_m", 7)), "Move the slider to the approximate draw depth from the canal, river, or farm channel.")
            ans = current_answers()

        if ans.get("job") == "drain_sewage":
            render_drain_quantity_slider(ans)
            render_drain_time_slider()
            render_question("Step 8", "What is the water quality / contents?", "c6_quality", C6_OPTIONS, "Choose what the pump is likely to handle.")
            ans = current_answers()
        elif ans.get("job") in {"lift_and_store", "boost_pressure"} and ans.get("source") and (ans.get("c0_destination") or ans.get("job") == "drain_sewage"):
            render_question("Step 6", "How much water is needed?", "demand", DEMAND_OPTIONS_BY_SETTING.get(ans.get("setting"), []), "Choose the closest daily water-use range.")
            ans = current_answers()

        if ans.get("job") == "boost_pressure" and ans.get("demand"):
            if ans.get("setting") == "farm":
                render_question("Pressure detail", "Fixture / application pressure class", "c5a_pressure", C5A_BY_SETTING.get(ans.get("setting"), []), "Choose the irrigation or farm application that needs pressure.")
                ans = current_answers()
                if ans.get("c5a_pressure"):
                    farm_options = FARM_C4_OPTIONS_BY_C5A.get(ans.get("c5a_pressure"), [])
                    farm_question = {
                        "farm_flood": "How many field outlets or furrow channels does this serve?",
                        "farm_drip": "How many drip zones or trough points does this serve?",
                        "farm_sprinkler": "How many sprinkler heads or wash-down points does this serve?",
                        "farm_rain_gun": "How many rain guns or high-pressure sprinklers does this serve?",
                    }.get(ans.get("c5a_pressure"), "How many farm application points does this serve?")
                    render_question("Pressure detail", farm_question, "c4_outlets", farm_options, "The count bands are tailored to the selected Farm pressure class.")
                    render_question("Pressure detail", "How many will run at the same time?", "c5_usage", C5_OPTIONS, "Choose the pattern that best matches peak farm use.")
            else:
                render_question("Pressure detail", "How many outlets or application points?", "c4_outlets", C4_OPTIONS, "Count the taps, fixtures, irrigation points, or application points that may need water.")
                render_question("Pressure detail", "How many will run at the same time?", "c5_usage", C5_OPTIONS, "Choose the pattern that best matches peak use at the site.")
                render_question("Pressure detail", "Fixture / application pressure class", "c5a_pressure", C5A_BY_SETTING.get(ans.get("setting"), []), "Choose the type of fixture, irrigation, or application that needs pressure.")
            ans = current_answers()

        maybe_render_water_scarcity(ans)
        ans = current_answers()

        if ready_for_power(ans):
            if ans.get("setting") and needs_phase_confirm(ans):
                render_question("Power detail", "Power supply phase", "c7_phase", C7_OPTIONS, "Choose the power supply available at the pump location.")
                ans = current_answers()

            if ans.get("setting") and c8_triggered(ans):
                render_question("Power detail", "Duty cycle", "c8_duty", C8_OPTIONS, "Choose how long the pump is expected to run on a busy day.")
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
                st.markdown('<div class="info-box">Continue by answering the next question.</div>', unsafe_allow_html=True)

    with right:
        st.markdown('<div class="side-stack">', unsafe_allow_html=True)
        render_vector_panel(vec)
        render_recommendations(scored, trace)
        st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
