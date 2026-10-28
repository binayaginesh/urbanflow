# UrbanFlow Stage B Handoff Note

**Author:** Swathy S Thankachi (MUT23CA068)  
**Recipient:** Alent Varkey (Stage C: Real Data, Calibration & Release), Team  
**Date:** 2026-10-28  
**Branch:** `stage-b-platform` (merged to `main`)  
**Git Tag:** `stage-b-done`  

---

## 1. Executive Summary & Deliverables

Stage B ("Dashboard, Visible Simulation, Validation Harness") delivers the complete interactive **UrbanFlow Command Center Platform** for Bengaluru urban traffic planners, connecting directly to the Stage A Simulation Engine and Decision Intelligence Layer.

### Delivered Components:
1. **Multi-Page Dark Command-Center Dashboard (`demo/app.py`, `src/urbanflow_data/dashboard_ui.py`)**:
   - **Command Center (`🎛️`)**: City-wide network topology, real-time KPI metrics, road hierarchy distribution, bottleneck hotspot identification.
   - **Scenario Lab (`🧪`)**: Non-destructive intervention testing (junction closures, flyover additions, VIP convoy diversions), before-and-after network maps, speed delta map, animated vehicle flow and congestion heatmap, MCDA composite scoring waterfall chart, traffic-light verdict card, and Monte Carlo stability confidence indicator.
   - **Compare & Recommend (`⚖️`)**: Multi-scenario performance matrix with side-by-side bar charts and autonomous "AI Suggests" Top-3 TOPSIS-ranked intervention recommendations.
   - **AI Insights (`💡`)**: Deterministic plain-language decision explanations (no LLM numeric hallucinations), Ridge Regression ML congestion forecasting by road class, and Isolation Forest simulation anomaly detection.
   - **Transit & Metro (`🚌`)**: BMTC bus route travel time & delay analysis, scenario link disruptions, and Namma Metro walk-radius interchange proximity.
   - **Validation Harness (`🛡️`)**: Observed vs simulated speed parity scatter, BPR error metrics (RMSE, MAE, MAPE, Pearson r), deterministic 70/30 hold-out corridor split, and bundle integrity test suite.
   - **Pipeline & Data Inspector (`🗄️`)**: Schema table browser, metadata (`metadata.json`), active configuration (`config.yaml`), and data dictionary reader.
2. **Offline & Demo Cache System (`src/urbanflow_data/dashboard_cache.py`)**:
   - `URBANFLOW_OFFLINE=1`: Eliminates tile server calls; renders using local coordinate projections.
   - `URBANFLOW_CACHE_MODE=1`: Disk-backed `.cache/` simulation storage for sub-second UI responsiveness.
   - Configurable `URBANFLOW_DATA_DIR` environment variable pointing to any processed data directory.
3. **PDF Decision Brief Generator (`src/urbanflow_data/report_generator.py`)**:
   - Executive PDF generation via ReportLab with tables, scoring, and plain-language justifications downloadable directly from Scenario Lab.
4. **Validation & Testing Harness (`src/urbanflow_data/validation_harness.py`, `tests/`)**:
   - 146 automated tests across Stage A and B (`pytest -q` passing).
   - Playwright end-to-end browser smoke testing suite capturing automated full-page screenshots in `docs/screenshots/`.

---

## 2. Instructions for Stage C (Alent Varkey)

### How to Point the Dashboard to Real Data:
Set the environment variable `URBANFLOW_DATA_DIR` before running the dashboard:
```bash
# Windows PowerShell
$env:URBANFLOW_DATA_DIR = "data/processed"
streamlit run demo/app.py

# Linux / macOS
export URBANFLOW_DATA_DIR="data/processed"
streamlit run demo/app.py
```

### Running Validation on Field Observations:
1. Deposit field observations into `data/raw/traffic/manual_observations_<name>.csv`.
2. The Validation Harness in `demo/app.py` (and `run_validation()`) will automatically split corridors 70/30 (calibration vs hold-out) using the deterministic seed in `config/config.yaml` (`validation.holdout_seed: 42`).
3. Set `validation.mape_target_pct` in `config/config.yaml` to activate pass/fail criteria on real data.

---

## 3. Verification & Acceptance Checklist

- [x] Streamlit dashboard with all 7 pages fully functional.
- [x] Visible simulation: Before/after maps, link delta map, animated flow heatmap.
- [x] Decision Intelligence: Composite score, 3-tier verdict, waterfall chart, Monte Carlo confidence.
- [x] "AI Suggests" Top-3 optimizer integrated.
- [x] PDF Planner Report generator working.
- [x] Offline mode and disk caching operating cleanly.
- [x] Data directory parameterized via `URBANFLOW_DATA_DIR`.
- [x] Playwright smoke tests and screenshot capture passing.
- [x] `python scripts/demo_check.py` passes cleanly.
- [x] Complete test suite passing (`142 passed, 4 skipped`).
