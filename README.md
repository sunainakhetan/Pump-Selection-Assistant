# Pump Selection Assistant

A free, web-based pump-selection tool. Customers answer a short questionnaire and get ranked pump recommendations from the current 4,056-row master catalogue stored in an Excel file.

The catalogue is the single source of truth for SKUs. The app looks for `FINAL_MASTER_DATASHEET_final.xlsx` first. If you keep the uploaded spreadsheet name, it can also fall back to `MASTER DATASHEET_final_final copy(7).xlsx`.

This build is aligned to the revised Framework v0.6 and the revised Filtering and Scoring mechanism.

## What you get

- Clean, step-by-step questionnaire with Setting asked first, followed by Job, Source, Lift, setting-specific Demand, and triggered conditional questions.
- Live invalidity enforcement: impossible answer combinations are greyed out with an explanation.
- Soft warnings for unusual but still allowed combinations.
- A transparent **requirement vector** built from the answers, shown in a collapsible panel.
- Framework v0.6 filtering and scoring using head, flow, phase, voltage, pump type, borewell diameter, suction lift, sewage/water-quality logic, and relevant type-specific filters.
- C5a fixture/application pressure handling for pressure jobs.
- C7 default-then-confirm phase logic.
- Always-triggered C9 voltage handling, with the correct C9 question shape based on Setting and final phase.
- Polished recommendation cards with score, head/flow ranges, HP, phase, voltage data, borewell diameter, pressure/tank/control fields where available, and warning flags.
- Catalogue-driven results — SKUs are read from Excel, not hard-coded into the app.

## What changed in this updated build

This update keeps the old README structure but updates the app behaviour to the new documents.

- Updated the customer journey to match Framework v0.6:
  - Setting → Job → Source → Lift → Demand → triggered conditional factors.
- Replaced the old generic demand labels with setting-specific demand bands.
- Updated the internal demand mapping:
  - representative daily volume,
  - default run-time,
  - minimum flow,
  - typical flow.
- Added **C5a — Fixture / Application Pressure Class** for pressure jobs.
- C5a now contributes head add-ons by setting/application.
- Home premium fixtures with 1–4 or 5–12 outlets also apply the 3,000 / 3,500 LPH flow floor.
- Replaced the older voltage logic with the revised C9 model:
  - Home / small-commercial single-phase: two-band voltage picker.
  - Farm single-phase: Min V / Max V range.
  - Three-phase variants: Min V / Max V range.
- Updated C7 phase logic:
  - Setting-based default phase.
  - Confirmation/override only when the framework requires it.
- Updated borewell casing/V-code handling, including additional V-codes present in the current catalogue.
- Updated C2 borewell depth and C3 open-well depth head add-ons.
- Updated ground-floor lift handling for below-grade sources:
  - Borewell + ground-floor lift is valid; C2 depth carries the below-ground lift.
  - Open well + ground-floor lift is valid; C3 depth carries the below-ground lift.
  - Underground sump + ground-floor lift is valid; the app adds the fixed sump-lift allowance.
- Added the underground-sump fixed head allowance:
  - +8 m to required minimum head.
  - +12 m to typical head.
- Updated source-to-pump-type mappings:
  - Underground sump/storage can feed Self-Priming, Openwell, Pressure Booster, or Hydropneumatic candidates depending on job type.
  - Municipal direct supply maps to Pressure Booster / Hydropneumatic candidates.
  - Sewage/drainage pit maps to Sewage Pump candidates.
- Added the Self-Priming RPM speed split for water-quality handling.
- Updated `_verify.py` to validate the revised worked example and the relaxed below-grade ground-floor lift cases.

## Files

```text
app.py                              — Streamlit UI
style.css                           — UI styling
vector.py                           — builds the requirement vector from customer answers
rules.py                            — Framework v0.6 invalidity and warning rules
scoring.py                          — filtering pipeline + scoring
_verify.py                          — verification script for the revised worked example
requirements.txt                    — Python dependencies
FINAL_MASTER_DATASHEET_final.xlsx   — pump catalogue, editable source of SKUs
config.toml                         — Streamlit theme config copy
.streamlit/config.toml              — Streamlit Cloud theme config location
```

## Running it locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

The app opens at:

```text
http://localhost:8501
```

## Deploying to Streamlit Community Cloud (free)

1. **Create a GitHub repo** and upload the project files:
   - `app.py`
   - `vector.py`
   - `rules.py`
   - `scoring.py`
   - `style.css`
   - `_verify.py`
   - `requirements.txt`
   - `.streamlit/config.toml`
   - the Excel catalogue file
2. Keep the Excel catalogue named `FINAL_MASTER_DATASHEET_final.xlsx` for the cleanest deployment. The app can also fall back to `MASTER DATASHEET_final_final copy(7).xlsx` if that is the file name you upload.
3. Go to Streamlit Community Cloud and sign in with your GitHub account.
4. Click **New app**.
5. Pick your repo.
6. Set the main file to:

```text
app.py
```

7. Click **Deploy**.
8. After a short build, Streamlit gives you a public URL similar to:

```text
https://your-pump-assistant.streamlit.app
```

## Updating the catalogue

This is the daily workflow once the app is deployed:

1. Open `FINAL_MASTER_DATASHEET_final.xlsx` in Excel on your computer.
2. Edit the catalogue.
3. Save the file.
4. On your GitHub repo page, drag-and-drop the updated file to replace the old one.
5. GitHub asks for a short commit message — anything is fine.
6. Streamlit Cloud detects the change and redeploys automatically.
7. The next visitor to the app sees the updated catalogue.

The app uses `@st.cache_data` keyed on the Excel file's modification time, so when the Excel file changes, the cache is invalidated automatically.

## Who can use the app

By default, a Streamlit Community Cloud app URL is **public**. Anyone with the link can use the app.

- **Just you?** Do not share the link.
- **Your office team?** Send them the link.
- **The general public?** Publish the link on your website or marketing material.

If you need a private app with login, Streamlit Community Cloud supports access control through GitHub-based permissions. Use Streamlit's current access-control settings for that.

## Verifying it works

The revised filtering/scoring document contains a fully worked example using the current 4,056-row catalogue. You can reproduce it through `_verify.py`.

Run:

```bash
python _verify.py
```

Expected highlights:

- Catalogue rows loaded: 4,056.
- Rows with usable Min/Max Head and Min/Max Flow: 4,025.
- Survivors after filtering: 114.
- The top five recommendations should be:

```text
1. CRI Pumps CRI4R-2N/3/35       — score 99
2. Kirloskar Brothers 80HHN-2024 — score 99
3. CRI Pumps CRI4R-2/3/40        — score 98
4. CRI Pumps CRI4R-2N/3/32       — score 98
5. CRI Pumps CRI4R-3E/5/40       — score 98
```

The same worked-example path is:

```text
Setting: Large commercial or institutional
Job: Lift and store
Source: Borewell
Lift: 11–15 floors
Demand: ~10,000–50,000 L/day — mid-size institutional premises
Destination: Overhead tank
Borewell casing: 6 inch
Borewell water depth: 200–300 ft
Power phase: Three-phase
Duty cycle: Heavy
Voltage Min V: 380 V
Voltage Max V: 430 V
```

For this example, the requirement vector should use approximately:

```text
Allowed pump types: Borewell Pump
Required minimum head: 135 m
Typical head: 145 m
Required minimum flow: 8,000 LPH
Typical flow: 12,000 LPH
Allowed phase: Three or Both
Voltage envelope: 380–430 V, three-phase
Preferred HP cap: none for Large commercial
```

The verification script also checks the revised below-grade ground-floor lift behaviour:

- Borewell → ground-floor lift-and-store is valid.
- Underground sump → ground-floor lift-and-pressurise is valid.
- Underground sump adds +8 m required head and +12 m typical head.
- Underground-sump pressure jobs can include Pressure Booster candidates.

## Source of truth

- **Catalogue rows:** `FINAL_MASTER_DATASHEET_final.xlsx`, sheet `Master Data`.
- **Framework:** `Pump_UseCase_Framework_v0_6_integrated_updates-3.docx`.
- **Filtering and scoring:** `Filtering_and_Scoring_Mechanism_revised-3.docx`.
- **Code implementation:** `vector.py`, `rules.py`, and `scoring.py`.

If a rule, threshold, mapping, or filter needs to change, update the relevant document and the corresponding constant or function in the code, then redeploy.

## Notes and caveats

- The scoring method uses catalogue Min/Max Head and Min/Max Flow ranges. It does not use full manufacturer pump curves.
- If true pump curves become available later, curve-based selection should replace midpoint scoring.
- Row counts and top-five results are tied to the current master sheet. If the catalogue changes, rerun `_verify.py` and update this README's expected counts if needed.
- Some catalogue rows may have missing voltage, phase, speed, pressure, or tank/control data. The matching engine handles these according to the revised rules and fallback logic.
