# Pump Selection Assistant

A free, web-based pump-selection tool. Customers answer a short questionnaire and get the top 5 best-matching pumps from a 4,020-SKU catalogue stored in an Excel file.

The catalogue (`FINAL_MASTER_DATASHEET_final.xlsx`) is the single source of truth. To update the pumps, edit the Excel file — the app picks up the changes automatically.

## What you get

- Clean, step-by-step questionnaire (5 core questions + conditionals shown only when needed)
- Live invalidity enforcement: impossible answer combinations are greyed out with an explanation
- A transparent **requirement vector** built from the answers, shown in a collapsible panel
- Twelve-step filter pipeline + midpoint scoring (60 head + 40 flow + bonuses − penalties)
- Polished recommendation cards with score, head/flow ranges, HP, phase, and any warning flags
- All 4,020 SKUs come from the Excel — nothing is hard-coded

## Files

```
app.py                              — Streamlit UI
vector.py                           — builds the requirement vector
rules.py                            — 74 invalidity rules from the framework doc
scoring.py                          — 12-step filter pipeline + midpoint scoring
requirements.txt                    — Python dependencies
FINAL_MASTER_DATASHEET_final.xlsx   — pump catalogue (editable)
```

## Running it locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

The app opens at `http://localhost:8501`.

## Deploying to Streamlit Community Cloud (free)

1. **Create a GitHub repo** and upload all four `.py` files, `requirements.txt`, and the Excel file. (You can drag-and-drop the files onto the repo page in your browser — no Git command line needed.)
2. **Go to** [share.streamlit.io](https://share.streamlit.io) and sign in with your GitHub account.
3. Click **"New app"**, pick your repo, set the main file to `app.py`, and click **Deploy**.
4. After ~2 minutes, you get a public URL like `https://your-pump-assistant.streamlit.app`.

## Updating the catalogue

This is the daily workflow once the app is deployed:

1. Open `FINAL_MASTER_DATASHEET_final.xlsx` in Excel on your computer.
2. Edit. Save.
3. On your GitHub repo page, drag-and-drop the updated file to replace the old one. GitHub asks for a short commit message — anything is fine.
4. Streamlit Cloud detects the change and redeploys in about 30 seconds.
5. The next visitor to the app sees the updated catalogue.

The app uses `@st.cache_data` keyed on the Excel file's modification time, so when the file changes the cache is invalidated automatically.

## Who can use the app

By default, the Streamlit Cloud URL is **public**. Anyone with the link can use the app.

- **Just you?** Don't share the link.
- **Your office team?** Send them the link.
- **The general public?** Just publish the link on your website.

If you ever need a private app with login, Streamlit Cloud's free plan also supports gating the app to specific GitHub users — see Streamlit's docs.

## Verifying it works

The filtering document contains a fully worked example in sections 9-15. Enter these answers to reproduce it:

- Job: Boost pressure from existing storage or supply
- Source: Overhead tank
- Lift: 3rd floor
- Demand: Medium
- Setting: Home
- Outlets: 5-12 outlets
- Usage: Moderate
- Phase: Single-phase
- Voltage: Normal voltage (200-240 V)

The app uses the representative outlet count for each outlet band. For the 5-12 outlets band, the representative count is 8.

For this example, the requirement vector should use:

- Required minimum head: 12 m
- Typical head: 18 m
- Required minimum flow: 2,500 LPH
- Typical flow: 3,500 LPH
- Allowed phase: Single or Both
- Preferred HP cap: 3 HP, with a hard cap at 6 HP

You should see 101 surviving SKUs after filtering. The top five should be:

1. Shakti SH4-3 — score 96
2. Shakti SHI4-3 — score 96
3. Shakti SHN4-3 — score 96
4. Kirloskar Brothers CPBS-62824H / V — score 94
5. Lubi MH 1A — score 93

You can also run `_verify.py` to print the requirement vector, filter trace, and top-five table from the Excel catalogue.

## Source of truth

- **Catalogue rows**: `FINAL_MASTER_DATASHEET_final.xlsx`, sheet `Master Data`.
- **Rules, mappings, filters, scoring**: the two Word documents (`Pump_UseCase_Framework___mapping_tables_FINAL.docx`, `FILTERING_AND_SCORING_MECHANISM_FINAL.docx`). All numbers in `vector.py`, `rules.py`, and `scoring.py` come from those documents — nothing is invented.

If a rule or threshold needs to change, update the relevant constant in `vector.py` or `rules.py` and the doc, then redeploy.
