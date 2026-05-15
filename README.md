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

The filtering doc contains a fully worked example (section 9–15) ending with the Lubi MH4-5B at score 97, 144 surviving candidates. Enter these answers to reproduce:

- Job: Boost pressure from existing storage or supply
- Source: Overhead tank
- Lift: 3rd floor
- Demand: Medium
- Setting: Home
- Outlets: 5–12 outlets (the underlying outlet count for the example is 6)
- Usage: Moderate
- Phase: Single-phase (default)
- Voltage: Normal voltage (200–240 V)

You should see Lubi MH4-5B at the top with score 97, and the filter trace should end at 144 rows. *(Note: the worked example in the doc explicitly uses an 18 m minimum / 25 m typical head for the 3rd-floor band to preserve its arithmetic. The standard mapping for 3rd floor is 12 m / 18 m; the app uses the standard mapping in production. To match the doc's exact 144-row count and top-5 list, you can verify against `_verify.py`.)*

## Source of truth

- **Catalogue rows**: `FINAL_MASTER_DATASHEET_final.xlsx`, sheet `Master Data`.
- **Rules, mappings, filters, scoring**: the two Word documents (`Pump_UseCase_Framework___mapping_tables_FINAL.docx`, `FILTERING_AND_SCORING_MECHANISM_FINAL.docx`). All numbers in `vector.py`, `rules.py`, and `scoring.py` come from those documents — nothing is invented.

If a rule or threshold needs to change, update the relevant constant in `vector.py` or `rules.py` and the doc, then redeploy.
