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
from scoring import filter_skus, lift_flags, score_skus
from vector import SETTING_DEFAULTS, build_vector

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
  --bg:#f6f8fb;
  --card:#ffffff;
  --ink:#0f172a;
  --muted:#64748b;
  --line:#e2e8f0;
  --cyan:#0891b2;
  --cyan-dark:#0e7490;
  --cyan-soft:#ecfeff;
  --cyan-pill:#cffafe;
  --shadow:0 12px 32px rgba(15,23,42,.08);
  --amber-bg:#fffbeb;
  --amber-border:#fde68a;
  --amber-ink:#92400e;
  --red-bg:#fef2f2;
  --red-border:#fecaca;
  --red-ink:#991b1b;
  --disabled:#f1f5f9;
  --disabled-text:#94a3b8;
}

html, body, [class*="css"] {
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
    "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}

body, .stApp { background: var(--bg); color: var(--ink); }
.block-container { padding-top:0 !important; padding-bottom:4rem; max-width:1280px; }
#MainMenu, footer, header { visibility:hidden; }
h1, h2, h3 { color: var(--ink); letter-spacing:-.035em; }

.hero-shell {
  margin:0 calc(50% - 50vw) 26px;
  padding:42px max(24px, calc(50vw - 640px)) 38px;
  background:linear-gradient(135deg,#ffffff 0%,#ecfeff 100%);
  border-bottom:1px solid var(--line);
}
.hero-grid { display:grid; grid-template-columns:minmax(0,1fr) 320px; gap:28px; align-items:center; }
.hero-badge {
  display:inline-flex; align-items:center; gap:8px;
  background:var(--cyan-pill); color:var(--cyan-dark);
  border-radius:999px; padding:8px 13px;
  font-size:.86rem; font-weight:800;
}
.hero-title {
  max-width:780px; margin:14px 0 14px;
  font-size:clamp(2.1rem,5vw,3.65rem); line-height:1.02;
  font-weight:900; letter-spacing:-.06em;
}
.hero-copy { max-width:780px; color:var(--muted); line-height:1.55; font-size:1.04rem; margin:0; }
.status-card {
  background:rgba(255,255,255,.78); border:1px solid var(--line);
  border-radius:24px; padding:18px; box-shadow:var(--shadow);
}
.status-row { display:flex; justify-content:space-between; gap:12px; font-weight:900; }
.progress-rail { height:10px; background:#e2e8f0; border-radius:999px; overflow:hidden; margin:12px 0 14px; }
.progress-fill { display:block; height:100%; background:var(--cyan); border-radius:999px; }
.pill-row { display:flex; flex-wrap:wrap; gap:8px; }
.ui-pill {
  display:inline-flex; align-items:center; gap:5px; border-radius:999px;
  background:#f1f5f9; color:#475569; padding:6px 10px;
  font-size:.76rem; font-weight:800;
}

.question-panel, .side-panel {
  background:var(--card); border:1px solid var(--line); border-radius:28px;
  box-shadow:var(--shadow); padding:20px; margin-bottom:18px;
}
.side-stack { position:sticky; top:18px; }
.step-badge {
  display:inline-block; color:var(--cyan); font-size:.78rem;
  font-weight:900; text-transform:uppercase; letter-spacing:.09em; margin-bottom:6px;
}
.section-title { font-size:1.38rem; font-weight:900; color:var(--ink); margin:0 0 6px; line-height:1.18; }
.section-help { font-size:.92rem; color:var(--muted); margin:0 0 14px; line-height:1.45; }

.option-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; margin-top:14px; }
.option-card {
  border:1px solid var(--line); background:#fff; border-radius:18px;
  padding:15px; min-height:136px; transition:.18s ease;
}
.option-card:hover { border-color:#67e8f9; background:#f8fafc; transform:translateY(-1px); }
.option-card.selected { border-color:var(--cyan); background:var(--cyan-soft); box-shadow:0 0 0 3px rgba(8,145,178,.12); }
.option-card.disabled { background:var(--disabled); border-color:#e5e7eb; color:var(--disabled-text); transform:none; opacity:.96; }
.option-label { font-weight:900; color:#1e293b; line-height:1.25; margin-bottom:6px; }
.option-desc { color:var(--muted); font-size:.86rem; line-height:1.36; margin-bottom:10px; }
.option-card.disabled .option-label { color:#64748b; }
.option-card.disabled .option-desc { color:#94a3b8; }
.option-reason { color:var(--red-ink); font-size:.76rem; line-height:1.35; margin-top:8px; font-weight:750; }
.selected-pill {
  display:inline-flex; background:#0f172a; color:#fff; border-radius:999px;
  padding:5px 9px; font-size:.72rem; font-weight:900; margin-top:4px;
}

.stButton > button {
  width:100%; border-radius:13px !important; font-weight:850 !important;
  border:1px solid var(--line) !important; min-height:38px;
}
.stButton > button:not(:disabled) {
  background:#ffffff !important; color:#0f172a !important;
}
.stButton > button:not(:disabled):hover {
  border-color:#67e8f9 !important; background:#f8fafc !important;
}
.stButton > button:disabled {
  background:#e2e8f0 !important; color:#94a3b8 !important;
}

.warning-box, .error-box, .info-box {
  border-radius:16px; padding:12px 13px; margin:12px 0;
  font-size:.9rem; line-height:1.42; border:1px solid;
}
.warning-box { background:var(--amber-bg); border-color:var(--amber-border); color:var(--amber-ink); }
.error-box { background:var(--red-bg); border-color:var(--red-border); color:var(--red-ink); }
.info-box { background:var(--cyan-soft); border-color:#a5f3fc; color:#155e75; }

.side-title-row { display:flex; justify-content:space-between; gap:16px; align-items:start; }
.side-title { margin:0; font-size:1.45rem; line-height:1.15; font-weight:900; }
.side-subtitle { margin:6px 0 0; color:var(--muted); line-height:1.45; }
.metric-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; margin-top:16px; }
.metric-card { background:#f8fafc; border:1px solid #edf2f7; border-radius:16px; padding:12px; min-height:84px; }
.metric-card small { display:block; color:var(--muted); font-size:.68rem; text-transform:uppercase; letter-spacing:.07em; font-weight:900; }
.metric-card strong { display:block; margin-top:5px; color:var(--ink); font-size:1.08rem; line-height:1.15; }
.metric-card span { display:block; margin-top:5px; color:var(--muted); font-size:.76rem; line-height:1.3; }
.vec-panel { background:#0f172a; color:#e2e8f0; border-radius:18px; padding:14px; font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:.78rem; overflow:auto; }

.stTextInput input {
  border-radius:15px !important; border:1px solid var(--line) !important;
  padding:12px 14px !important; box-shadow:none !important;
}
.rec-card { background:#fff; border:1px solid var(--line); border-radius:18px; padding:14px; margin-top:12px; box-shadow:none; }
.rec-top { display:flex; justify-content:space-between; gap:12px; align-items:flex-start; }
.rec-card .score-pill { background:#0f172a; color:#fff; border-radius:13px; padding:7px 10px; font-weight:900; font-size:.82rem; white-space:nowrap; }
.rec-card .brand-sku { font-size:1.05rem; font-weight:900; line-height:1.25; color:var(--ink); }
.rec-card .type-line { font-size:.82rem; color:var(--muted); margin-top:3px; }
.rec-card .rank { color:var(--cyan-dark); font-weight:900; margin-right:6px; }
.rec-card .specs { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px; margin-top:12px; }
.rec-card .spec-box { background:#f8fafc; border-radius:12px; padding:9px; }
.rec-card .spec-label { color:var(--muted); font-size:.64rem; text-transform:uppercase; letter-spacing:.06em; font-weight:900; }
.rec-card .spec-value { color:var(--ink); font-weight:850; margin-top:3px; font-size:.82rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.flag-pill { display:inline-block; background:var(--amber-bg); color:var(--amber-ink); border:1px solid var(--amber-border); border-radius:999px; padding:4px 8px; font-size:.72rem; font-weight:800; margin:8px 6px 0 0; }
.empty-card { border:1px dashed #cbd5e1; border-radius:18px; background:#f8fafc; text-align:center; padding:22px; color:var(--muted); margin-top:14px; }

@media(max-width:980px) { .hero-grid { grid-template-columns:1fr; } .side-stack { position:static; } }
@media(max-width:620px) {
  .hero-shell { padding:28px 16px; }
  .option-grid, .metric-grid, .rec-card .specs { grid-template-columns:1fr; }
  .question-panel, .side-panel { border-radius:22px; padding:16px; }
}
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
C7_OPTIONS = [("Single", "Single-phase"), ("Three", "Three-phase")]
C8_OPTIONS = [
    ("moderate", "Moderate (2–6 hours/day)"),
    ("heavy", "Heavy (6–12 hours/day)"),
    ("continuous", "Continuous (12+ hours/day)"),
]
C9_OPTIONS = [
    ("very_low", "Very low voltage"),
    ("low", "Low voltage"),
    ("normal", "Normal voltage"),
]

OPTION_DESCRIPTIONS = {
    "job": {
        "lift_and_store": "Pull water from a source (well, borewell, sump, etc.) and fill a tank for later use.",
        "lift_and_pressurise_directly": "Pull water from a source and feed taps, fixtures, or lines directly under pressure, with no storage in between.",
        "boost_pressure": "Water is already available (overhead tank, sump, municipal line); the pump only needs to give it more force at the outlets.",
        "drain_water": "Clear water from basements, lift pits, drainage pits, or rainwater collection points.",
        "pump_sewage": "Empty septic tanks, sewage pits, kitchen waste collection, or toilet waste.",
    },
    "source": {
        "borewell": "Deep underground source with a narrow casing pipe.",
        "open_well": "Open water body, typically shallow, accessible from the top.",
        "underground_sump": "Ground-level or below-ground storage filled by tanker, municipal line, or other source.",
        "overhead_tank": "Tank already at height; water needs pressure rather than lifting.",
        "municipal": "Direct connection from city water supply.",
        "sewage_pit": "Collection point for waste water, sewage, or storm drainage.",
        "open_ground": "Surface water sources used mainly for irrigation.",
    },
    "lift": {
        "ground": "Same level, ground floor only, or pressure-only requirement.",
        "floor_1": "Water needs to reach the first floor.",
        "floor_2": "Water needs to reach the second floor.",
        "floor_3": "Water needs to reach the third floor.",
        "floor_4": "Water needs to reach the fourth floor.",
        "floors_5_10": "Low-rise apartment, small hotel, hostel, school, or commercial building.",
        "floors_11_15": "Mid-rise apartment, hotel, hostel, school, or commercial building.",
        "floors_16_25": "High-rise residential or commercial building; may require staged pumping.",
        "floors_26_40": "Tall residential or mixed-use towers; multiple booster zones.",
        "floors_41_60": "Skyscraper-class buildings; dedicated transfer pumps per zone.",
        "floors_above_60": "Super-tall buildings; custom hydraulic schemes by consultants.",
    },
    "demand": {
        "very_small": "Single-bathroom shop, kiosk, very small home, single-person dwelling.",
        "small": "Nuclear family home with 1–2 bathrooms, small office, small clinic.",
        "medium": "Larger home with 3–4 bathrooms, joint family, small guesthouse, small restaurant, small farm plot.",
        "large": "Small apartment block (10–30 flats), mid-size hotel, hostel, school, mid-size farm, small factory.",
        "very_large": "Large apartment complex, large hotel, hospital, large school or college, large farm, factory.",
        "bulk": "Township, multi-tower complex, industrial estate, very large institutional campus.",
    },
    "setting": {
        "home": "Any residence — independent house, villa, flat, farmhouse.",
        "farm": "Irrigation, crop watering, livestock, agricultural property.",
        "shop_small_comm": "Showrooms, small offices, clinics, restaurants, small retail.",
        "large_commercial": "Hotels, hospitals, schools, hostels, apartment blocks, colleges.",
        "light_industry": "Factories, warehouses, construction projects, light manufacturing.",
    },
    "c0_destination": {
        "overhead_tank": "Roof or elevated tank that gravity-feeds the building afterward. Most common destination for domestic lift-and-store.",
        "ground_sump": "Intermediate storage at ground or below-ground level; usually feeds another pump downstream.",
        "direct_pipes": "Pump runs on demand and feeds the plumbing directly under pressure; no intermediate storage.",
        "irrigation": "Sprinklers, drip systems, flood irrigation, paddy fields, troughs, or open agricultural channels.",
        "industrial_process": "Cooling, washing, processing lines, RO plants, water softeners, or STP feed.",
        "tanker": "Water loaded into a tanker, drum, or other vessel for transport elsewhere.",
    },
    "c1_casing": {
        "casing_4in": "Most common for shallow domestic borewells.",
        "casing_6in": "Most common for deeper domestic and small commercial borewells.",
        "casing_8in": "Commercial, agricultural, and deep borewells.",
        "casing_10in": "Large agricultural, industrial, and very deep borewells.",
        "casing_12in_plus": "Industrial or municipal borewells.",
    },
    "c2_depth": {
        "under_50ft": "Water level near the surface.",
        "50_100ft": "Water level near the surface.",
        "100_200ft": "Typical depth for many domestic borewells.",
        "200_300ft": "Typical depth for many domestic borewells.",
        "300_450ft": "Deeper borewells, often in low-water-table regions.",
        "450_600ft": "Deeper borewells, often in low-water-table regions.",
        "600_800ft": "Very deep domestic or agricultural borewells.",
        "800_1000ft": "Very deep domestic or agricultural borewells.",
        "above_1000ft": "Industrial, large agricultural, or special-case borewells.",
    },
    "c3_well_depth": {
        "shallow_under_30ft": "Most domestic open wells in high-water-table regions.",
        "medium_30_60ft": "Typical open wells in many parts of India.",
        "deep_above_60ft": "Older or rural open wells in dry regions.",
    },
    "c4_outlets": {
        "1_4": "Single bathroom or kitchen booster.",
        "5_12": "Small home with 2–3 bathrooms.",
        "13_20": "Large home, small commercial.",
        "21_35": "Large home with multiple suites, small hotel floor, clinic.",
        "36_75": "Mid-size hotel, small hostel, office floor.",
        "76_150": "Large hotel, apartment block, institution.",
        "above_150": "Large complex, multi-tower, campus.",
    },
    "c5_usage": {
        "light": "Most outlets used one at a time (small home).",
        "moderate": "Half the outlets typically running together (family home, small office).",
        "heavy": "Many outlets running together (hotel, hostel, large office).",
        "constant_peak": "Full simultaneous demand expected (commercial kitchen, public facility).",
    },
    "c6_quality": {
        "clean_water": "Basement seepage, rainwater, clear groundwater.",
        "lightly_soiled": "Bathwater, laundry, mild grey water.",
        "solids_waste": "Kitchen waste, fibrous matter, light sewage.",
        "heavy_sewage": "Septic tank contents, toilet waste with solids.",
        "industrial_effluent": "Chemical, abrasive, or specialised duty (out of normal scope).",
    },
    "c7_phase": {
        "Single": "Standard home connection, 230V.",
        "Three": "Farm, factory, commercial connection, 415V.",
    },
    "c8_duty": {
        "moderate": "Large home, small commercial, small farm.",
        "heavy": "Hotel, mid-size farm, factory shift.",
        "continuous": "Industrial process, high-rise booster, large agricultural.",
    },
    "c9_voltage": {
        "very_low": "Below 180V. Site experiences deep voltage sags; only wide-range single-phase pumps will run reliably.",
        "low": "180V–200V. Site supply is regularly below the nominal 220–240V band; pump must tolerate a wide low-end voltage range.",
        "normal": "200V–240V. Standard residential and small-commercial supply; no additional voltage-tolerance constraint required.",
    },
}

FIELD_ORDER = [
    "job", "source", "lift", "demand", "setting",
    "c0_destination", "c1_casing", "c2_depth", "c3_well_depth",
    "c4_outlets", "c4_outlets_count", "c5_usage", "c6_quality",
    "c7_phase", "c8_duty", "c9_voltage",
]


# ---------------------------------------------------------------------------
# State + rendering helpers
# ---------------------------------------------------------------------------

def init_state():
    if "answers" not in st.session_state:
        st.session_state.answers = {}


def current_answers() -> dict:
    return dict(st.session_state.answers)


def reset_app():
    st.session_state.answers = {}
    for key in list(st.session_state.keys()):
        if key.startswith("select_") or key == "rec_search":
            del st.session_state[key]


def set_answer(field: str, value, payload=None):
    answers = dict(st.session_state.answers)
    previous = answers.get(field)

    # If an upstream answer changes, remove downstream answers immediately so
    # the next render can grey out newly incompatible options correctly.
    if previous != value and field in FIELD_ORDER:
        start = FIELD_ORDER.index(field)
        for downstream in FIELD_ORDER[start:]:
            answers.pop(downstream, None)

    answers[field] = value
    if field == "c4_outlets":
        if payload is not None:
            answers["c4_outlets_count"] = payload
        else:
            answers.pop("c4_outlets_count", None)

    st.session_state.answers = answers


def option_description(field: str, option_id: str) -> str:
    return OPTION_DESCRIPTIONS.get(field, {}).get(option_id, "")


def render_option(field: str, opt, ans: dict):
    oid, label = opt[0], opt[1]
    payload = opt[2] if len(opt) > 2 else None
    disabled, reason = is_disabled(field, oid, ans)
    selected = ans.get(field) == oid

    classes = ["option-card"]
    if selected:
        classes.append("selected")
    if disabled:
        classes.append("disabled")

    st.markdown(
        f"""
        <div class="{' '.join(classes)}">
          <div class="option-label">{label}</div>
          <div class="option-desc">{option_description(field, oid)}</div>
          {f'<div class="selected-pill">Selected</div>' if selected else ''}
          {f'<div class="option-reason">Unavailable: {reason}</div>' if disabled and reason else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.button(
        "Selected" if selected else "Select",
        key=f"select_{field}_{oid}",
        disabled=disabled or selected,
        on_click=set_answer,
        args=(field, oid, payload),
        use_container_width=True,
    )


def render_question(step: str, title: str, field: str, options, help_text: str = ""):
    ans = current_answers()
    st.markdown('<div class="question-panel">', unsafe_allow_html=True)
    st.markdown(f'<div class="step-badge">{step}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)
    if help_text:
        st.markdown(f'<div class="section-help">{help_text}</div>', unsafe_allow_html=True)

    st.markdown('<div class="option-grid">', unsafe_allow_html=True)
    for i in range(0, len(options), 2):
        row = st.columns(2)
        for j, col in enumerate(row):
            idx = i + j
            if idx < len(options):
                with col:
                    render_option(field, options[idx], ans)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


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
    flag_pills = "".join(f'<span class="flag-pill">{f.replace("_", " ")}</span>' for f in flags)

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
            <div class="spec-box"><div class="spec-label">HP</div><div class="spec-value">{row['HP']}</div></div>
            <div class="spec-box"><div class="spec-label">Head</div><div class="spec-value">{head_str}</div></div>
            <div class="spec-box"><div class="spec-label">Flow</div><div class="spec-value">{flow_str}</div></div>
            <div class="spec-box"><div class="spec-label">Phase</div><div class="spec-value">{phase}</div></div>
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

    for rank, (_, row) in enumerate(view.head(20).iterrows(), start=1):
        render_card(rank, row, lift_flag_list)

    if len(view) == 0:
        st.markdown('<div class="empty-card">No recommendations match this search.</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


def required_fields(ans: dict):
    fields = ["job", "source", "lift", "demand", "setting"]

    if ans.get("job") in {"lift_and_store", "lift_and_pressurise_directly"}:
        fields.append("c0_destination")
    if ans.get("source") == "borewell":
        fields += ["c1_casing", "c2_depth"]
    if ans.get("source") == "open_well":
        fields.append("c3_well_depth")
    if ans.get("job") in {"boost_pressure", "lift_and_pressurise_directly"}:
        fields += ["c4_outlets", "c5_usage"]
    if ans.get("job") in {"drain_water", "pump_sewage"}:
        fields.append("c6_quality")

    if ans.get("setting") and ans.get("lift") and ans.get("demand"):
        needs_phase_confirm = (
            (ans["setting"] == "home" and (
                ans["lift"] in {"floors_5_10", "floors_11_15", "floors_16_25", "floors_26_40", "floors_41_60", "floors_above_60"}
                or ans["demand"] in {"large", "very_large", "bulk"}
                or ans.get("c2_depth") in {"300_450ft", "450_600ft", "600_800ft", "800_1000ft", "above_1000ft"}
            ))
            or ans["setting"] == "shop_small_comm"
        )
        if needs_phase_confirm:
            fields.append("c7_phase")

    if ans.get("setting") in {"farm", "light_industry", "large_commercial"} or ans.get("demand") in {"large", "very_large", "bulk"}:
        fields.append("c8_duty")

    final_phase = ans.get("c7_phase")
    if not final_phase and ans.get("setting"):
        final_phase = SETTING_DEFAULTS[ans["setting"]][0]
    if final_phase == "Single":
        fields.append("c9_voltage")

    return fields


def is_complete(ans: dict):
    fields = required_fields(ans)
    return all(ans.get(f) is not None for f in fields), fields


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
                Incompatible options are disabled immediately using the built-in invalidity rules.
              </p>
            </div>
            <div class="status-card">
              <div class="status-row"><span>Progress</span><span>{progress_pct}%</span></div>
              <div class="progress-rail"><span class="progress-fill" style="width:{progress_pct}%"></span></div>
              <div class="pill-row">
                <span class="ui-pill">{sku_count:,} SKUs loaded</span>
                <span class="ui-pill">Rules enabled</span>
              </div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def auto_fill_phase(ans: dict) -> dict:
    ans = dict(ans)
    if ans.get("setting") and "c7_phase" not in ans:
        needs_phase_confirm = False
        if ans.get("lift") and ans.get("demand"):
            needs_phase_confirm = (
                (ans["setting"] == "home" and (
                    ans["lift"] in {"floors_5_10", "floors_11_15", "floors_16_25", "floors_26_40", "floors_41_60", "floors_above_60"}
                    or ans["demand"] in {"large", "very_large", "bulk"}
                    or ans.get("c2_depth") in {"300_450ft", "450_600ft", "600_800ft", "800_1000ft", "above_1000ft"}
                ))
                or ans["setting"] == "shop_small_comm"
            )
        if not needs_phase_confirm:
            ans["c7_phase"] = SETTING_DEFAULTS[ans["setting"]][0]
    return ans


# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------

def main():
    init_state()

    try:
        sku_count = len(get_catalogue())
    except Exception:
        sku_count = 0

    ans_for_progress = auto_fill_phase(current_answers())
    complete, fields = is_complete(ans_for_progress)
    answered = sum(1 for f in fields if ans_for_progress.get(f) is not None)
    progress_pct = int(answered / len(fields) * 100) if fields else 0
    render_hero(progress_pct, sku_count)

    left, right = st.columns([1.85, 1], gap="large")

    with left:
        render_question(
            "Step 1 of 5 · Job",
            "What is the pump supposed to do?",
            "job",
            JOB_OPTIONS,
            "Pick the job that best describes what you need the pump for.",
        )
        render_question("Step 2 of 5 · Source", "Where is the water coming from?", "source", SOURCE_OPTIONS)
        render_question("Step 3 of 5 · Lift", "How high does the water need to go?", "lift", LIFT_OPTIONS)
        render_question("Step 4 of 5 · Demand", "How much water is needed?", "demand", DEMAND_OPTIONS)
        render_question("Step 5 of 5 · Setting", "What kind of place is it?", "setting", SETTING_OPTIONS)

        ans = current_answers()

        if ans.get("job") in {"lift_and_store", "lift_and_pressurise_directly"}:
            render_question("Additional detail", "Where does the water end up?", "c0_destination", DEST_OPTIONS)

        ans = current_answers()
        if ans.get("source") == "borewell":
            render_question("Additional detail", "Borewell casing diameter", "c1_casing", C1_OPTIONS)
            render_question(
                "Additional detail",
                "Borewell water depth (static rest level)",
                "c2_depth",
                C2_OPTIONS,
                "The depth from ground to the top of the water column when the pump is off — not the total drilled depth.",
            )

        ans = current_answers()
        if ans.get("source") == "open_well":
            render_question("Additional detail", "Open well water depth", "c3_well_depth", C3_OPTIONS)

        ans = current_answers()
        if ans.get("job") in {"boost_pressure", "lift_and_pressurise_directly"}:
            render_question("Additional detail", "Number of outlets", "c4_outlets", C4_OPTIONS)
            render_question("Additional detail", "How simultaneously are outlets used?", "c5_usage", C5_OPTIONS)

        ans = current_answers()
        if ans.get("job") in {"drain_water", "pump_sewage"}:
            render_question("Additional detail", "Water quality / contents", "c6_quality", C6_OPTIONS)
            if ans.get("c6_quality") == "industrial_effluent":
                st.markdown(
                    '<div class="error-box">⚠ <b>Specialised pump required.</b> Industrial effluent is outside the scope of this catalogue. Please consult a specialist.</div>',
                    unsafe_allow_html=True,
                )

        ans = current_answers()
        if ans.get("setting") and ans.get("lift") and ans.get("demand"):
            default_phase, _ = SETTING_DEFAULTS[ans["setting"]]
            needs_phase_confirm = (
                (ans["setting"] == "home" and (
                    ans["lift"] in {"floors_5_10", "floors_11_15", "floors_16_25", "floors_26_40", "floors_41_60", "floors_above_60"}
                    or ans["demand"] in {"large", "very_large", "bulk"}
                    or ans.get("c2_depth") in {"300_450ft", "450_600ft", "600_800ft", "800_1000ft", "above_1000ft"}
                ))
                or ans["setting"] == "shop_small_comm"
            )
            if needs_phase_confirm:
                render_question(
                    "Additional detail",
                    f"Power supply phase (default for this setting: {default_phase}-phase)",
                    "c7_phase",
                    C7_OPTIONS,
                    "Please confirm or override the default — small commercial connections vary.",
                )
            else:
                set_answer("c7_phase", default_phase)

        ans = current_answers()
        if ans.get("setting") in {"farm", "light_industry", "large_commercial"} or ans.get("demand") in {"large", "very_large", "bulk"}:
            render_question("Additional detail", "Duty cycle (hours per day)", "c8_duty", C8_OPTIONS)

        ans = auto_fill_phase(current_answers())
        if ans.get("c7_phase") == "Single":
            render_question(
                "Additional detail",
                "Lowest voltage at pump site",
                "c9_voltage",
                C9_OPTIONS,
                "What is the lowest voltage you usually get at the pump site?",
            )

        show_soft_warnings(auto_fill_phase(current_answers()))

    vec = None
    scored = None
    trace = []
    l_flags = []
    final_ans = auto_fill_phase(current_answers())
    complete, _ = is_complete(final_ans)

    try:
        if complete and final_ans.get("c6_quality") != "industrial_effluent":
            vec = build_vector(final_ans)
            df = get_catalogue()
            survivors, trace = filter_skus(df, vec)
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
            st.markdown(f'<div class="warning-box">ℹ <b>{code}:</b> {msg}</div>', unsafe_allow_html=True)

        render_recommendations(scored, l_flags)

        if trace:
            with st.expander("Show filter trace"):
                for t in trace:
                    st.text(f"Step {t['step']} : {t['label']} → {t['rows_left']} rows")
        st.markdown('</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
