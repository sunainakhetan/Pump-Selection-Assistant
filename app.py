"""Streamlit Pump Selection Assistant aligned to Framework v0.6."""

import os
from pathlib import Path

import pandas as pd
import streamlit as st

from rules import evaluate
from scoring import filter_skus, lift_flags, score_skus
from vector import (
    SETTING_DEFAULTS,
    build_vector,
    c8_triggered,
    c9_variant,
    default_phase,
    needs_phase_confirm,
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


# ---------------------------------------------------------------------------
# Extra CSS for clickable option cards
# ---------------------------------------------------------------------------

COMPACT_CARD_CSS = """

<style>
/* Clickable option boxes — clean 2-column layout */
[class*="st-key-optwrap_"] .stButton {
  height: 100%;
}

[class*="st-key-optwrap_"] .stButton > button {
  min-height: 218px !important;
  height: auto !important;
  width: 100% !important;
  padding: 26px 30px !important;
  border-radius: 24px !important;
  text-align: left !important;
  white-space: normal !important;
  line-height: 1.36 !important;
  font-size: 1.02rem !important;
  font-weight: 500 !important;
  background: #ffffff !important;
  border: 1px solid var(--line, #e2e8f0) !important;
  color: var(--ink, #0f172a) !important;
  box-shadow: none !important;
  display: flex !important;
  align-items: flex-start !important;
  justify-content: flex-start !important;
  overflow: visible !important;
}

[class*="st-key-optwrap_"] .stButton > button div,
[class*="st-key-optwrap_"] .stButton > button p {
  width: 100% !important;
  margin: 0 !important;
  padding: 0 !important;
  text-align: left !important;
  white-space: normal !important;
  overflow-wrap: anywhere !important;
  word-break: normal !important;
}

[class*="st-key-optwrap_"] .stButton > button strong {
  display: block !important;
  margin-bottom: 18px !important;
  font-size: calc(1.02rem + 2pt) !important;
  line-height: 1.24 !important;
  font-weight: 900 !important;
  color: var(--ink, #0f172a) !important;
}

[class*="st-key-optwrap_"] .stButton > button:hover:not(:disabled) {
  border-color: #67e8f9 !important;
  background: #f8fafc !important;
  transform: translateY(-1px);
}

[class*="st-key-optwrap_"] .stButton > button:disabled {
  background: #f8fafc !important;
  color: #94a3b8 !important;
  border-color: #e2e8f0 !important;
}

[class*="st-key-optwrap_"] .stButton > button:disabled strong {
  color: #94a3b8 !important;
}

.compact-question-panel {
  padding-bottom: 18px;
}

.detailed-rec-card {
  padding: 16px;
}

.detailed-specs {
  grid-template-columns: repeat(3, minmax(0, 1fr)) !important;
}

.detailed-specs .spec-box {
  min-height: 62px;
}

@media(max-width: 1100px) {
  .detailed-specs {
    grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
  }
}

@media(max-width: 700px) {
  .detailed-specs {
    grid-template-columns: 1fr !important;
  }

  [class*="st-key-optwrap_"] .stButton > button {
    min-height: 170px !important;
    padding: 22px 24px !important;
  }
}
.warning-pill {
  display: inline-flex;
  align-items: center;
  margin: 8px 0 14px 0;
  padding: 10px 14px;
  border-radius: 999px;
  background: #fff7ed;
  border: 1px solid #fed7aa;
  color: #9a3412;
  font-weight: 750;
  font-size: 0.86rem;
  line-height: 1.25;
}
</style>
"""
st.markdown(COMPACT_CARD_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Options
# ---------------------------------------------------------------------------

SETTING_OPTIONS = [
    ("home", "Home"),
    ("farm", "Farm / agriculture"),
    ("shop_small_comm", "Shop / office / small commercial"),
    ("large_commercial", "Large commercial or institutional"),
    ("light_industry", "Light industry / warehouse / construction site"),
]

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
    ("open_ground", "Open ground water"),
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

DEMAND_DESCRIPTIONS_BY_SETTING = {
    "home": {
        "vol_200": "1 resident. Single-person flat or studio, typically 1 bathroom, minimal kitchen use.",
        "vol_800": "2–5 residents. Small family with 1 bathroom, compact flat, regular kitchen and laundry use.",
        "vol_2000": "5–15 residents. Family with 2–4 bathrooms, larger flat or villa, possibly a small garden.",
        "vol_5000": "Large home or farmhouse with 5+ bathrooms, garden, car-wash area, pool top-up, or staff quarters.",
    },
    "farm": {
        "vol_800": "Small homestead or farmhouse domestic use only. No field irrigation.",
        "vol_2000": "Larger homestead or backyard livestock only, with troughs or hand-watered garden.",
        "vol_10000": "Very small irrigated plot or small dairy. Drip up to ~⅓ acre or sprinkler up to ~¼ acre.",
        "vol_50000": "Small-to-mid irrigated farm. Drip ~⅓–1.5 acres or sprinkler ~¼–1 acre.",
        "vol_200000": "Mid-to-large commercial farm with drip, sprinkler, flood/furrow, or large livestock use.",
        "vol_above_200000": "Large farm, estate, plantation, major irrigation, or major livestock operation.",
    },
    "shop_small_comm": {
        "vol_200": "Kiosk or single-staff outlet with 1–2 staff and one shared washroom.",
        "vol_800": "Small shop or compact office with 3–15 staff, 1–2 washrooms, and pantry.",
        "vol_2000": "Mid-size office, clinic, or retail premises with 15–40 staff and 2–4 washrooms.",
        "vol_5000": "Large office floor or small restaurant with multiple washrooms, canteen, or kitchen use.",
        "vol_10000": "Large standalone commercial premises, mid-size restaurant, guesthouse, or banquet hall.",
    },
    "large_commercial": {
        "vol_5000": "Very small institution: small apartment block, budget hotel, school block, hostel, or washroom block.",
        "vol_10000": "Small institution: apartment block, hotel, school, hostel, or small nursing home.",
        "vol_50000": "Mid-size institution: apartment block, hotel, school, hostel, or 25–100 bed hospital.",
        "vol_200000": "Large institution: large apartment block, hotel, campus, hostel block, or hospital.",
        "vol_above_200000": "Very large institution: multi-tower complex, township, large campus, or major hospital.",
    },
    "light_industry": {
        "vol_800": "Small workshop or storage shed with 5–15 workers and minimal process water.",
        "vol_2000": "Small factory or warehouse with 15–40 workers, basic canteen, and occasional washing.",
        "vol_5000": "Mid-size factory or active site with canteen, wash-down, or light process water.",
        "vol_10000": "Large factory or major construction site with significant wash-down or process water.",
        "vol_50000": "Mid-size industrial unit with production-line water, cooling, washing, or batching.",
        "vol_200000": "Large industrial unit with continuous-flow production water, cooling towers, or wash-down.",
        "vol_above_200000": "Industrial estate, major process plant, or very large infrastructure project.",
    },
}

DEST_OPTIONS = [
    ("overhead_tank", "Overhead tank"),
    ("ground_sump", "Ground-level storage tank or sump"),
    ("direct_pipes", "Direct to building pipes"),
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
    ("under_50ft", "Under 50 ft"),
    ("50_100ft", "50–100 ft"),
    ("100_200ft", "100–200 ft"),
    ("200_300ft", "200–300 ft"),
    ("300_450ft", "300–450 ft"),
    ("450_600ft", "450–600 ft"),
    ("600_800ft", "600–800 ft"),
    ("800_1000ft", "800–1,000 ft"),
    ("above_1000ft", "Above 1,000 ft"),
]

C3_OPTIONS = [
    ("shallow_under_30ft", "Shallow open well"),
    ("medium_30_60ft", "Medium open well"),
    ("deep_above_60ft", "Deep open well"),
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
    ("light", "Light"),
    ("moderate", "Moderate"),
    ("heavy", "Heavy"),
    ("constant_peak", "Constant peak"),
]

C6_OPTIONS = [
    ("clean_water", "Clean water"),
    ("lightly_soiled", "Lightly soiled"),
    ("solids_waste", "Solids and waste"),
    ("heavy_sewage", "Heavy sewage"),
    ("industrial_effluent", "Industrial effluent"),
]

C7_OPTIONS = [
    ("Single", "Single-phase"),
    ("Three", "Three-phase"),
]

C8_OPTIONS = [
    ("moderate", "Moderate"),
    ("heavy", "Heavy"),
    ("continuous", "Continuous"),
]

C9_BAND_OPTIONS = [
    ("single_low_under_200", "Below 200 V"),
    ("single_normal_200_240", "200–240 V"),
]

THREE_MIN_OPTIONS = [(v, f"{v} V") for v in [340, 350, 360, 370, 380, 390, 400, 410]]
THREE_MAX_OPTIONS = [(v, f"{v} V") for v in [380, 390, 400, 410, 420, 430, 440]]
FARM_SINGLE_MIN_OPTIONS = [(v, f"{v} V") for v in [140, 150, 160, 170, 180, 190, 200, 210, 220]]
FARM_SINGLE_MAX_OPTIONS = [(v, f"{v} V") for v in [190, 200, 210, 220, 230, 240]]

C5A_BY_SETTING = {
    "home": [
        ("home_standard", "Standard fittings"),
        ("home_premium", "Premium fittings"),
    ],
    "shop_small_comm": [
        ("shop_standard", "Standard fittings"),
        ("shop_premium", "Premium fittings"),
    ],
    "large_commercial": [
        ("large_comm_standard", "Standard fittings only"),
        ("large_comm_premium", "Premium guest-room / spa / pool fittings"),
    ],
    "farm": [
        ("farm_flood", "Flood, furrow, or hand-watering"),
        ("farm_drip", "Drip irrigation or livestock troughs"),
        ("farm_sprinkler", "Sprinklers or general wash-down"),
        ("farm_rain_gun", "Rain guns or high-pressure sprinklers"),
    ],
    "light_industry": [
        ("industry_standard", "Washroom and canteen only"),
        ("industry_light_wash", "Light wash-down"),
        ("industry_routine_wash", "Routine production wash"),
        ("industry_heavy_jetting", "Heavy wash-down or jetting"),
    ],
}

OPTION_DESCRIPTIONS = {
    "setting": {
        "home": "Any residence — independent house, villa, flat, or farmhouse.",
        "farm": "Irrigation, crop watering, livestock, or agricultural property.",
        "shop_small_comm": "Showrooms, small offices, clinics, restaurants, or small retail.",
        "large_commercial": "Hotels, hospitals, schools, hostels, apartment blocks, or colleges.",
        "light_industry": "Factories, warehouses, construction projects, or light manufacturing.",
    },
    "job": {
        "lift_and_store": "Pull water from a source and fill a tank for later use.",
        "lift_and_pressurise_directly": "Pull water from a source and feed taps, fixtures, or lines directly under pressure.",
        "boost_pressure": "Water is already available; the pump only needs to increase outlet pressure.",
        "drain_water": "Clear water from basements, lift pits, drainage pits, or rainwater collection points.",
        "pump_sewage": "Empty septic tanks, sewage pits, kitchen waste collection, or toilet waste.",
    },
    "source": {
        "borewell": "Deep underground source with a narrow casing pipe.",
        "open_well": "Open water body, typically shallow and accessible from the top.",
        "underground_sump": "Ground-level or below-ground storage filled by tanker, municipal line, or other source.",
        "overhead_tank": "Tank already at height; water needs pressure rather than lifting.",
        "municipal": "Direct connection from city water supply.",
        "sewage_pit": "Collection point for waste water, sewage, or storm drainage.",
        "open_ground": "Canal, river, pond, or farm channel used mainly for irrigation.",
    },
    "lift": {
        "ground": "Same level, ground floor only, or pressure-only requirement.",
        "floor_1": "Water needs to reach the first floor.",
        "floor_2": "Water needs to reach the second floor.",
        "floor_3": "Water needs to reach the third floor.",
        "floor_4": "Water needs to reach the fourth floor.",
        "floors_5_10": "Low-rise apartment, small hotel, hostel, school, or commercial building.",
        "floors_11_15": "Mid-rise apartment, hotel, hostel, school, or commercial building.",
        "floors_16_25": "High-rise building; staged pumping may be recommended.",
        "floors_26_40": "Tall tower; multi-zone booster scheme likely.",
        "floors_41_60": "Skyscraper-class building; consultant review recommended.",
        "floors_above_60": "Super-tall building; custom engineering normally required.",
    },
    "c0_destination": {
        "overhead_tank": "Roof or elevated tank that gravity-feeds the building afterward.",
        "ground_sump": "Intermediate storage at ground or below-ground level.",
        "direct_pipes": "Pump runs on demand and feeds plumbing directly under pressure.",
        "irrigation": "Sprinklers, drip systems, flood irrigation, fields, troughs, or livestock.",
        "industrial_process": "Cooling, washing, process lines, RO plants, water softeners, or STP feed.",
        "tanker": "Water loaded into a tanker, drum, or other transfer vessel.",
    },
    "c1_casing": {
        "casing_4in": "Most common for shallow domestic borewells.",
        "casing_6in": "Common for deeper domestic and small commercial borewells.",
        "casing_8in": "Commercial, agricultural, and deep borewells.",
        "casing_10in": "Large agricultural, industrial, and very deep borewells.",
        "casing_12in_plus": "Industrial or municipal borewells.",
    },
    "c2_depth": {
        "under_50ft": "Water level close to ground level.",
        "50_100ft": "Shallow borewell, common for many domestic sites.",
        "100_200ft": "Typical domestic borewell depth.",
        "200_300ft": "Deeper domestic borewell, often in drier areas.",
        "300_450ft": "Low-water-table borewell, common in deeper domestic or farm use.",
        "450_600ft": "High-head borewell, often used for farm or large-property supply.",
        "600_800ft": "High-head agricultural or large-property borewell.",
        "800_1000ft": "High-head borewell, usually agricultural or institutional.",
        "above_1000ft": "Industrial, large agricultural, or special-case borewell.",
    },
    "c3_well_depth": {
        "shallow_under_30ft": "Under 30 ft. Most domestic open wells in high-water-table regions.",
        "medium_30_60ft": "30–60 ft. Typical open wells in many parts of India.",
        "deep_above_60ft": "Above 60 ft. Older or rural open wells in dry regions.",
    },
    "c4_outlets": {
        "1_4": "Single bathroom or kitchen booster.",
        "5_12": "Small home with 2–3 bathrooms.",
        "13_20": "Large home or small commercial premises.",
        "21_35": "Large home with suites, small hotel floor, or clinic.",
        "36_75": "Mid-size hotel, small hostel, or office floor.",
        "76_150": "Large hotel, apartment block, or institution.",
        "above_150": "Large complex, multi-tower project, or campus.",
    },
    "c5_usage": {
        "light": "Most outlets used one at a time.",
        "moderate": "About half the outlets may run together.",
        "heavy": "Many outlets may run together.",
        "constant_peak": "Full simultaneous demand is expected.",
    },
    "c5a_pressure": {
        "home_standard": "Normal taps, showers, WCs, and kitchen use.",
        "home_premium": "Rain shower, body jets, or large overhead shower.",
        "shop_standard": "Taps, WCs, pantry, and basic washrooms.",
        "shop_premium": "Salon, spa, boutique-hotel showers, or clinic rinse points.",
        "large_comm_standard": "Standard taps, WCs, pantries, wards, offices, or classrooms.",
        "large_comm_premium": "Hotel suites, spa areas, pool-deck hose, rain showers, or body jets.",
        "farm_flood": "Flood, furrow, or hand-watering only.",
        "farm_drip": "Drip irrigation or livestock troughs.",
        "farm_sprinkler": "Sprinklers or wash-down for fields, sheds, or dairy parlour.",
        "farm_rain_gun": "Rain guns or high-pressure sprinklers.",
        "industry_standard": "Washroom and canteen use only.",
        "industry_light_wash": "Floors, equipment, and general housekeeping.",
        "industry_routine_wash": "Process water lines and regular plant wash-down.",
        "industry_heavy_jetting": "Intensive cleaning, heavy wash-down, or high-pressure jetting.",
    },
    "c6_quality": {
        "clean_water": "Basement seepage, rainwater, or clear groundwater.",
        "lightly_soiled": "Bathwater, laundry, or mild grey water.",
        "solids_waste": "Kitchen waste, fibrous matter, or light sewage.",
        "heavy_sewage": "Septic tank contents or toilet waste with solids.",
        "industrial_effluent": "Chemical, abrasive, or specialised duty outside normal catalogue scope.",
    },
    "c7_phase": {
        "Single": "Standard home connection, typically 230 V.",
        "Three": "Farm, factory, or commercial connection, typically 415 V.",
    },
    "c8_duty": {
        "moderate": "Typical domestic, small commercial, or small farm use.",
        "heavy": "Apartment, hotel, mid-size farm, or factory-shift use.",
        "continuous": "Industrial process, high-rise booster, or large agricultural use.",
    },
    "c9_voltage_band": {
        "single_low_under_200": "Supply commonly sags below 200 V at the pump site.",
        "single_normal_200_240": "Standard residential or small-commercial supply.",
    },
}

FIELD_ORDER = [
    "setting",
    "job",
    "source",
    "lift",
    "demand",
    "c0_destination",
    "c1_casing",
    "c2_depth",
    "c3_well_depth",
    "c4_outlets",
    "c4_outlets_count",
    "c5_usage",
    "c5a_pressure",
    "c6_quality",
    "c7_phase",
    "c8_duty",
    "c9_voltage_band",
    "c9_min_v",
    "c9_max_v",
]

PRESSURE_JOBS = {"boost_pressure", "lift_and_pressurise_directly"}
IGNORED_INCOMPLETE_RULE_IDS = {61, 74, 76}


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

def init_state():
    if "answers" not in st.session_state:
        st.session_state.answers = {}


def current_answers():
    return dict(st.session_state.answers)


def reset_app():
    st.session_state.answers = {}
    for key in list(st.session_state.keys()):
        if key.startswith("select_") or key.startswith("optwrap_") or key == "rec_search":
            del st.session_state[key]


def set_answer(field, value, payload=None):
    ans = dict(st.session_state.answers)
    previous = ans.get(field)

    if previous != value and field in FIELD_ORDER:
        for downstream in FIELD_ORDER[FIELD_ORDER.index(field):]:
            ans.pop(downstream, None)

    ans[field] = value

    if field == "c4_outlets":
        ans["c4_outlets_count"] = payload

    st.session_state.answers = ans


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def option_description(field: str, option_id) -> str:
    ans = current_answers()

    if field == "demand":
        setting = ans.get("setting")
        return DEMAND_DESCRIPTIONS_BY_SETTING.get(setting, {}).get(option_id, "")

    if field == "c9_min_v":
        return "Lowest voltage usually available at the pump site."

    if field == "c9_max_v":
        return "Highest voltage usually available at the pump site."

    return OPTION_DESCRIPTIONS.get(field, {}).get(option_id, "")


def disabled_reason_for_candidate(field: str, candidate_value, ans: dict):
    test = dict(ans)
    test[field] = candidate_value

    existing_hard = {
        rule_id
        for rule_id, severity, _ in evaluate(ans)
        if severity == "hard" and rule_id not in IGNORED_INCOMPLETE_RULE_IDS
    }

    for rule_id, severity, reason in evaluate(test):
        if severity != "hard":
            continue
        if rule_id in IGNORED_INCOMPLETE_RULE_IDS:
            continue
        if rule_id not in existing_hard:
            return reason

    return None


def render_option(field: str, opt, ans: dict, force_disabled_reason: str | None = None):
    oid, label = opt[0], opt[1]
    payload = opt[2] if len(opt) > 2 else None

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
            args=(field, oid, payload),
            use_container_width=True,
        )


def render_question(
    step: str,
    title: str,
    field: str,
    options,
    help_text: str = "",
    force_disabled_reason: str | None = None,
    columns_per_row: int = 2,
):
    ans = current_answers()

    st.markdown('<div class="question-panel compact-question-panel">', unsafe_allow_html=True)
    st.markdown(f'<div class="step-badge">{step}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)

    if help_text:
        st.markdown(f'<div class="section-help">{help_text}</div>', unsafe_allow_html=True)

    for i in range(0, len(options), columns_per_row):
        cols = st.columns(columns_per_row, gap="small")
        for col, opt in zip(cols, options[i:i + columns_per_row]):
            with col:
                render_option(field, opt, ans, force_disabled_reason=force_disabled_reason)

    st.markdown("</div>", unsafe_allow_html=True)


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
        if c9_variant(ans["setting"], phase) == "single_band":
            fields += ["c9_voltage_band"]
        else:
            fields += ["c9_min_v", "c9_max_v"]

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
    st.markdown(
        f"""
        <div class="hero-shell">
          <div class="hero-grid">
            <div>
              <div class="hero-badge">💧 Pump-selection assistant</div>
              <div class="hero-title">Choose a pump from the updated catalogue.</div>
              <p class="hero-copy">
                Answer a few questions and get the best-matching pumps from the current SKU catalogue.
                The matcher follows Framework v0.6, including setting-specific demand, C5a, and revised C9 voltage logic.
              </p>
            </div>
            <div class="status-card">
              <div class="status-row"><span>Progress</span><span>{progress_pct}%</span></div>
              <div class="progress-rail"><span class="progress-fill" style="width:{progress_pct}%"></span></div>
              <div class="pill-row">
                <span class="ui-pill">{sku_count:,} SKUs loaded</span>
                <span class="ui-pill">v0.6 rules enabled</span>
              </div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_c9(ans):
    phase = ans.get("c7_phase") or default_phase(ans["setting"])
    variant = c9_variant(ans["setting"], phase)

    if variant == "single_band":
        render_question(
            "Additional detail",
            "Voltage at pump site",
            "c9_voltage_band",
            C9_BAND_OPTIONS,
            "Home / small-commercial single-phase uses the two-band C9 picker.",
        )

    elif variant == "farm_single_range":
        render_question(
            "Additional detail",
            "Lowest single-phase voltage",
            "c9_min_v",
            FARM_SINGLE_MIN_OPTIONS,
            "Pick the lowest voltage usually available at the pump site.",
        )
        render_question(
            "Additional detail",
            "Highest single-phase voltage",
            "c9_max_v",
            FARM_SINGLE_MAX_OPTIONS,
            "Pick the highest voltage usually available at the pump site.",
        )

    else:
        render_question(
            "Additional detail",
            "Lowest three-phase voltage",
            "c9_min_v",
            THREE_MIN_OPTIONS,
            "Pick the lowest three-phase voltage usually available at the pump site.",
        )
        render_question(
            "Additional detail",
            "Highest three-phase voltage",
            "c9_max_v",
            THREE_MAX_OPTIONS,
            "Pick the highest three-phase voltage usually available at the pump site.",
        )


def show_soft_warnings(ans):
    for rid, sev, reason in evaluate(ans):
        if sev == "soft":
            st.markdown(
                f'<div class="warning-box">⚠ Rule #{rid}: {reason}</div>',
                unsafe_allow_html=True,
            )


def render_vector_panel(vec):
    st.markdown('<div class="side-panel">', unsafe_allow_html=True)
    st.markdown(
        '<h2 class="side-title">Requirement vector</h2>'
        '<p class="side-subtitle">Live hydraulic target used by the matcher.</p>',
        unsafe_allow_html=True,
    )

    if not vec:
        st.markdown(
            '<div class="empty-card">Complete the questions to build the vector.</div>',
            unsafe_allow_html=True,
        )

    else:
        st.markdown('<div class="metric-grid">', unsafe_allow_html=True)

        metrics = [
            ("Pump types", ", ".join(vec["allowed_pump_types"]) or "None", "Allowed set"),
            ("Head", f"{vec['required_min_head']:.0f} / {vec['typical_head']:.0f} m", "Min / typical"),
            ("Flow", f"{vec['required_min_flow']:.0f} / {vec['typical_flow']:.0f} LPH", "Min / typical"),
            ("Phase", vec["final_phase"], "Final C7"),
        ]

        for label, value, sub in metrics:
            st.markdown(
                f"""
                <div class="metric-card">
                  <small>{label}</small>
                  <strong>{value}</strong>
                  <span>{sub}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("</div>", unsafe_allow_html=True)

        with st.expander("Raw vector"):
            st.json(vec)

    st.markdown("</div>", unsafe_allow_html=True)


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

    return (
        f'<div class="spec-box">'
        f'<div class="spec-label">{label}</div>'
        f'<div class="spec-value">{clean_value(value)}</div>'
        f'</div>'
    )


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

    pump_diameter = row.get("Pump Diameter")
    boxes.append(spec_item("Pump diameter", pump_diameter))

    if is_real_value(pump_diameter) and str(pump_diameter).strip().upper() == "V3":
        boxes.append(spec_item("V3 type", row.get("V3 Type")))

    boxes.append(
        spec_range(
            "Single-phase voltage",
            row,
            "Single Phase Minimum Voltage",
            "Single Phase Maximum Voltage",
            " V",
        )
    )
    boxes.append(
        spec_range(
            "Three-phase voltage",
            row,
            "Three Phase Minimum Voltage",
            "Three Phase Maximum Voltage",
            " V",
        )
    )

    extra_columns = [
        ("Outlet size", "Outlet Size", ""),
        ("Suction lift", "Suction Lift (m)", " m"),
        ("Speed", "Speed (RPM)", " RPM"),
        ("Cutter type", "Cutter Type", ""),
        ("Cooling type", "Cooling Type", ""),
        ("Stage", "Stage", ""),
        ("Motor type", "Motor Type", ""),
        ("Material", "Material", ""),
        ("Application", "Application", ""),
        ("Model", "Model", ""),
        ("Series", "Series", ""),
        ("Power rating", "Power Rating", ""),
        ("Discharge size", "Discharge Size", ""),
    ]

    for label, col, suffix in extra_columns:
        if col in row.index:
            value = row.get(col)
            if is_real_value(value):
                boxes.append(spec_item(label, f"{clean_value(value)}{suffix}"))

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
              <div class="brand-sku">
                <span class="rank">#{rank}</span>{row.get('Brand', '')} {row.get('SKU', '')}
              </div>
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
    if scored is None or len(scored) == 0 or "Type" not in scored.columns:
        return False

    return scored["Type"].astype(str).str.lower().str.contains("borewell", na=False).any()


def render_recommendations(scored):
    st.markdown('<div class="side-panel">', unsafe_allow_html=True)
    st.markdown(
        '<h2 class="side-title">Recommendations</h2>'
        '<p class="side-subtitle">Top 20 matches from the updated catalogue.</p>',
        unsafe_allow_html=True,
    )

    if has_borewell_recommendations(scored):
        st.markdown(
            """
            <div class="warning-pill">
              If your borewell is prone to sand shedding, we recommend using a compressor pump.
            </div>
            """,
            unsafe_allow_html=True,
        )

    if scored is None:
        st.markdown(
            '<div class="empty-card">Recommendations appear after all required answers are complete.</div>',
            unsafe_allow_html=True,
        )

    elif len(scored) == 0:
        st.markdown(
            '<div class="empty-card">No SKUs survived the current filters.</div>',
            unsafe_allow_html=True,
        )

    else:
        search = st.text_input("Search recommendations", key="rec_search", placeholder="Brand or SKU")
        view = scored

        if search:
            brand = view["Brand"].astype(str) if "Brand" in view.columns else pd.Series("", index=view.index)
            sku = view["SKU"].astype(str) if "SKU" in view.columns else pd.Series("", index=view.index)
            mask = brand.str.contains(search, case=False, na=False) | sku.str.contains(search, case=False, na=False)
            view = view[mask]

        st.markdown(
            f'<div class="info-box">{len(scored):,} SKUs survived. Showing top 20.</div>',
            unsafe_allow_html=True,
        )

        for i, (_, row) in enumerate(view.head(20).iterrows(), 1):
            render_card(i, row)

    st.markdown("</div>", unsafe_allow_html=True)
    

# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------

def main():
    init_state()

    try:
        sku_count = len(get_catalogue())
    except Exception:
        sku_count = 0

    progress_ans = auto_fill_phase(current_answers())
    complete, fields = is_complete(progress_ans)

    progress_pct = (
        int(sum(1 for f in fields if progress_ans.get(f) is not None) / len(fields) * 100)
        if fields
        else 0
    )

    render_hero(progress_pct, sku_count)

    left, right = st.columns([1.85, 1], gap="large")

    with left:
        ans = current_answers()

        render_question(
            "Step 1 of 5 · Setting",
            "What kind of place is it?",
            "setting",
            SETTING_OPTIONS,
            "",
        )

        ans = current_answers()

        render_question(
            "Step 2 of 5 · Job",
            "What is the pump supposed to do?",
            "job",
            JOB_OPTIONS,
        )

        ans = current_answers()

        render_question(
            "Step 3 of 5 · Source",
            "Where is the water coming from?",
            "source",
            SOURCE_OPTIONS,
        )

        ans = current_answers()

        render_question(
            "Step 4 of 5 · Lift",
            "How high does the water need to go?",
            "lift",
            LIFT_OPTIONS,
        )

        ans = current_answers()

        if ans.get("setting"):
            demand_options = DEMAND_OPTIONS_BY_SETTING[ans["setting"]]
            demand_help = "Demand bands are setting-specific and change based on the selected Setting."
            demand_disabled_reason = None
        else:
            demand_options = [("placeholder", "Select a setting to see the correct demand bands")]
            demand_help = ""
            demand_disabled_reason = "Select Setting first."

        render_question(
            "Step 5 of 5 · Demand",
            "How much water is needed?",
            "demand",
            demand_options,
            demand_help,
            force_disabled_reason=demand_disabled_reason,
        )

        ans = current_answers()

        if ans.get("job") in {"lift_and_store", "lift_and_pressurise_directly"}:
            render_question(
                "Additional detail",
                "Where does the water end up?",
                "c0_destination",
                DEST_OPTIONS,
            )

        ans = current_answers()

        if ans.get("source") == "borewell":
            render_question(
                "Additional detail",
                "Borewell casing diameter",
                "c1_casing",
                C1_OPTIONS,
            )
            render_question(
                "Additional detail",
                "Borewell water depth",
                "c2_depth",
                C2_OPTIONS,
                "Static rest level — depth to the top of water when the pump is off.",
            )

        ans = current_answers()

        if ans.get("source") == "open_well":
            render_question(
                "Additional detail",
                "Open well water depth",
                "c3_well_depth",
                C3_OPTIONS,
            )

        ans = current_answers()

        if ans.get("job") in PRESSURE_JOBS:
            render_question(
                "Additional detail",
                "Number of outlets",
                "c4_outlets",
                C4_OPTIONS,
            )
            render_question(
                "Additional detail",
                "How simultaneously are outlets used?",
                "c5_usage",
                C5_OPTIONS,
            )
            if ans.get("setting"):
                render_question(
                    "Additional detail",
                    "Fixture / application pressure class",
                    "c5a_pressure",
                    C5A_BY_SETTING[ans["setting"]],
                    "C5a adds pressure head. For small homes with premium fittings, it also applies a flow floor.",
                )

        ans = current_answers()

        if ans.get("job") in {"drain_water", "pump_sewage"}:
            render_question(
                "Additional detail",
                "Water quality / contents",
                "c6_quality",
                C6_OPTIONS,
            )

            if ans.get("c6_quality") == "industrial_effluent":
                st.markdown(
                    '<div class="error-box">⚠ <b>Specialised pump required.</b> Industrial effluent is outside catalogue scope.</div>',
                    unsafe_allow_html=True,
                )

        ans = current_answers()

        if ans.get("setting") and ans.get("lift") and ans.get("demand"):
            if needs_phase_confirm(ans):
                render_question(
                    "Additional detail",
                    f"Power supply phase",
                    "c7_phase",
                    C7_OPTIONS,
                    f"Default for this setting: {default_phase(ans['setting'])}-phase.",
                )
            elif "c7_phase" not in ans:
                set_answer("c7_phase", default_phase(ans["setting"]))

        ans = current_answers()

        if ans.get("setting") and ans.get("demand") and c8_triggered(ans):
            render_question(
                "Additional detail",
                "Duty cycle",
                "c8_duty",
                C8_OPTIONS,
            )

        ans = auto_fill_phase(current_answers())

        if ans.get("setting") and ans.get("c7_phase"):
            render_c9(ans)

        show_soft_warnings(auto_fill_phase(current_answers()))

    final_ans = auto_fill_phase(current_answers())
    complete, _ = is_complete(final_ans)

    vec = None
    scored = None
    trace = []
    l_flags = []

    try:
        if complete and final_ans.get("c6_quality") != "industrial_effluent":
            vec = build_vector(final_ans)
            survivors, trace = filter_skus(get_catalogue(), vec)
            scored = score_skus(survivors, vec)
            l_flags = lift_flags(final_ans)

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

        render_recommendations(scored)

        if trace:
            with st.expander("Show filter trace"):
                for t in trace:
                    st.text(f"Step {t['step']} : {t['label']} → {t['rows_left']} rows")

        st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
