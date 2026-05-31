# Pump Selection Assistant v1.2

A Streamlit pump-selection assistant rebuilt for the updated **Pump Use-Case Framework v1.2** and **Filtering and Scoring Mechanism v1.2**.

The app asks a guided, setting-first questionnaire, converts answers into a requirement vector, surfaces the requirement matrix in the UI, filters the master catalogue, and ranks matching pump SKUs.

## Included files

```text
app.py                              Streamlit UI
style.css                           Visual styling
vector.py                           v1.2 requirement-vector builder and matrix
rules.py                            v1.2 validity, trigger, and warning rules
scoring.py                          v1.2 filtering and scoring pipeline
_verify.py                          smoke/logic verification checks
requirements.txt                    Python dependencies
FINAL_MASTER_DATASHEET_final.xlsx   Master catalogue copied from the uploaded database
.streamlit/config.toml              Streamlit theme configuration
docs/                               Uploaded v1.2 framework/scoring documents
