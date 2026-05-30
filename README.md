# Pump Selection Assistant v1.1

A Streamlit pump-selection assistant rebuilt end-to-end for the updated **Pump Use-Case Framework v1.1** and **Filtering and Scoring Mechanism v1.1**.

The app asks customers a guided questionnaire, converts their answers into a requirement vector, filters the current master catalogue, and ranks matching pump SKUs.

## Included files

```text
app.py                              Streamlit UI
style.css                           Existing visual styling, preserved
vector.py                           v1.1 requirement-vector builder and matrix
rules.py                            v1.1 validity, trigger, and warning rules
scoring.py                          v1.1 filtering and scoring pipeline
_verify.py                          smoke/logic verification checks
requirements.txt                    Python dependencies
FINAL_MASTER_DATASHEET_final.xlsx   Master catalogue copied from the uploaded database
.streamlit/config.toml              Streamlit theme configuration
docs/                               Uploaded v1.1 framework/scoring documents
```

## v1.1 alignment highlights

* Three-job model only: **Lift and store**, **Boost pressure**, **Drain sewage / water**.
* Setting-first flow, with downstream Source and Destination options filtered by the enabled Setting × Job × Source × Destination matrix.
* Destination is asked only for Lift-and-store and Boost-pressure paths.
* Lift is conditionally triggered and hidden for ground-sump fill, irrigation, and ordinary drainage paths.
* C2, C3, and C3G are continuous metre sliders, not depth bands.
* Open-ground-water C3G 7 m rule is implemented:

  * `≤ 7 m`: Self-Priming candidates, depth treated as suction lift.
  * `> 7 m`: Openwell candidates, depth added to head.
* Fixed `+3 m` underground-sump allowance.
* Consolidated head formula with friction applied once.
* Boost-pressure C4 / C5 / C5a cluster and setting-specific C5a options.
* Drain job uses a water-removal-rate band instead of the normal demand table.
* C6 water-quality/cutter logic for sewage candidates.
* C7 default-then-confirm phase logic, including larger-installation Home confirmation.
* C8 duty-cycle trigger logic.
* C9 voltage variant selection and corrected contain-test: pump envelope must contain the entered site range.
* Home and Shop / office / small commercial 3 HP soft cap and 6 HP hard cap.
* Water-scarcity advisory and Self-Priming slow-speed ranking promotion.

## Running locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Open the local Streamlit URL shown in the terminal, usually:

```text
http://localhost:8501
```

## Verifying the package

Run:

```bash
python _verify.py
```

The bundled verification currently checks:

* v1.1 matrix generation and availability helpers.
* The v1.1 large-commercial borewell lift-and-store worked-example path.
* The open-ground-water 7 m boundary rule.
* Drain sewage / water candidate type and cutter logic.

On the uploaded catalogue, the verification passed with 4,056 catalogue rows loaded and 4,025 rows with usable Min/Max Head and Min/Max Flow.

## Deployment notes

For Streamlit Community Cloud, upload the complete package to GitHub and set the main file to:

```text
app.py
```

Keep the catalogue file named:

```text
FINAL_MASTER_DATASHEET_final.xlsx
```

The app caches the Excel load using the file modification time, so updating the catalogue file and redeploying will refresh results.

## Notes

The scoring engine uses catalogue Min/Max Head and Min/Max Flow ranges. It does not use full manufacturer pump curves. If curve data becomes available later, replace midpoint scoring with curve-based selection.
