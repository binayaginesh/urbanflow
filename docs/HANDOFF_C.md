# UrbanFlow Stage C Handoff & v1.0 Release Note

**Author:** Alent Varkey (Stage C: Real Data, Calibration, Final Integration & Release)  
**Team:** Mehrin (Stage A), Swathy S Thankachi (Stage B), Alent Varkey (Stage C)  
**Date:** 2026-10-29  
**Branch:** `stage-c-release` (merged to `main`)  
**Git Tag:** `v1.0`  

---

## 1. Executive Summary & v1.0 Deliverables

Stage C completes the end-to-end **UrbanFlow Bengaluru Decision Intelligence & Traffic Simulation Platform (v1.0)** by replacing the synthetic demo network with a real OpenStreetMap road network for the **Silk Board – BTM Layout – Madiwala – HSR Layout** corridor, integrating BMTC bus routes and Namma Metro stations, calibrating the BPR and Decision Intelligence layers, and validating the complete software stack.

### Delivered Components in Stage C:
1. **Real Bengaluru OSM Road Network (`src/urbanflow_data/osm_download.py`, `clean_network.py`, `build_graph.py`, `export.py`)**:
   - Downloaded real drivable OpenStreetMap network via Overpass API (`bbox: 12.910–12.930 N, 77.610–77.630 E`): `903` raw OSM nodes and `1,849` raw edges cleaned, consolidated (`15 m` tolerance), and filtered to the largest strongly connected component (**`220` junctions, `673` directed edges, `65.3 km`** total road length).
   - Applied manual corridor overrides (`road_overrides.corridors` in `config/config.yaml`) across `75` major arterial edges (`Hosur Road`, `Outer Ring Road`, `Sarjapura Road`, `Mahayogi Vemana Road`, `Maruthi Nagar Main Road`, `16th Main Road`) and annotated `7` real signalised landmark junctions (`Node 48 Silk Board Flyover North`, `Node 69 BTM Udupi Garden Signal`, `Node 161 Madiwala Market Junction`, `Node 2 Krupanidhi Junction`, `Node 37 BTM Water Tank Circle`, `Node 52 Madiwala Police Station Junction`, `Node 109 Hosur Road - St Johns Approach`).
2. **Public Transit & Multimodal Integration (`src/urbanflow_data/transit.py`)**:
   - Built `5` curated BMTC bus routes (`500D`, `356C`, `201R`, `25A`, `G3`), `8/8` snapped bus stops (`<= 12.1 m`), and **`94` contiguous route-edges** map-matched along shortest paths on the real OSM graph.
   - Added `4` Namma Metro Yellow/Blue Line stations (`Central Silk Board Metro`, `BTM Layout Metro`, `Jayadeva Hospital Metro`, `HSR Layout Metro`) in `metro_stations.parquet`.
3. **BPR Calibration, Single-Source Routing Optimization & Real Bundle Export (`calibrate.py`, `simulation_engine.py`, `validate.py`)**:
   - Wired deterministic 70/30 corridor hold-out split into `calibrate.py` and `traffic_baseline.py`.
   - Upgraded `DemandMatrix._build()` and `FlowAssigner.assign()` in `src/urbanflow_data/simulation_engine.py` to use single-source Dijkstra (`nx.single_source_dijkstra_path_length` and `nx.single_source_dijkstra_path`) with path-hop demand scaling, reducing 220-node simulation runtime from ~30s to **~0.12s** while keeping realistic network congestion ratios (`1.54x` morning peak, `1.95x` evening peak).
   - Passed **11/11** automated pipeline validation checks (`python -m urbanflow_data.cli validate`).
4. **Scenario Library, Events, VIP Routes, Demand Zones & Threshold Calibration (`scripts/run_library.py`, `scripts/calibrate_thresholds.py`)**:
   - Added real Bengaluru corridor `events`, `vip_routes`, and `demand_zones` to `config/config.yaml` (leaving unknown civil monetary costs as `estimated_cost_inr_crore: null`).
   - Verified empirically via `scripts/run_library.py` and `scripts/calibrate_thresholds.py` (`docs/library_results.json`) that all three verdict tiers (`RECOMMENDED`, `MODERATE`, `NOT RECOMMENDED`) are naturally represented across peak hours (`RECOMMENDED: 2`, `MODERATE: 5`, `NOT RECOMMENDED: 7`).
5. **ML Component Evaluation & Honest Validation Documentation (`scripts/evaluate_ml.py`, `docs/VALIDATION.md`, `docs/LIMITATIONS.md`, `docs/calibration_report.md`, `data/PROVENANCE.md`)**:
   - Evaluated `CongestionTrendPredictor` (Ridge regression) on a 70/30 hold-out split (`471` train edges / `202` hold-out edges): Ridge ML achieved **RMSE = `0.1075`, MAE = `0.0684`, MAPE = `4.69%`**, beating both the road-class mean baseline (`RMSE = 0.2603`) and global mean baseline (`RMSE = 0.3184`) by >58%.

---

## 2. Running UrbanFlow v1.0 on Real Data

```powershell
# 1. Verify processed real bundle integrity (11/11 checks)
.venv\Scripts\python.exe -m urbanflow_data.cli validate

# 2. Run smoke check & top-3 optimizer on real Bengaluru network
$env:URBANFLOW_DATA_DIR = "data/processed"
.venv\Scripts\python.exe scripts/demo_check.py
.venv\Scripts\python.exe scripts/run_optimizer.py --slot morning_peak

# 3. Run full scenario library, threshold calibration, and ML evaluation
.venv\Scripts\python.exe scripts/run_library.py
.venv\Scripts\python.exe scripts/calibrate_thresholds.py
.venv\Scripts\python.exe scripts/evaluate_ml.py

# 4. Launch the 7-page Streamlit Command Center Dashboard
$env:URBANFLOW_DATA_DIR = "data/processed"
.venv\Scripts\streamlit.exe run demo/app.py
```

---

## 3. Release Acceptance Checklist (`v1.0`)

- [x] Real Bengaluru OSM network downloaded, cleaned, consolidated (`220` nodes, `673` edges, `65.3 km`).
- [x] Manual corridor overrides (`75` edges) and `7` signalised landmark junctions applied.
- [x] BMTC bus routes (`5` routes, `8` stops, `94` contiguous route-edges) and Namma Metro stations (`4` stations) exported.
- [x] `python -m urbanflow_data.cli validate` passes `11/11` checks.
- [x] Events, VIP routes, demand zones, and `null` unverified costs configured in `config/config.yaml`.
- [x] `scripts/run_library.py` and `scripts/calibrate_thresholds.py` confirm all 3 verdict tiers (`RECOMMENDED`, `MODERATE`, `NOT RECOMMENDED`).
- [x] `scripts/evaluate_ml.py` confirms `CongestionTrendPredictor` beats naive baselines on 70/30 hold-out split.
- [x] Honest documentation completed in `docs/VALIDATION.md`, `docs/calibration_report.md`, `docs/LIMITATIONS.md`, `docs/BLOCKERS.md`, and `data/PROVENANCE.md`.
- [x] Full automated test suite passing (`147 passed` across unit, integration, and Stage C suites).
