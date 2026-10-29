# UrbanFlow Validation Report (Stage C)

**Date:** 2026-10-29  
**Stage Owner:** Alent Varkey (Stage C — Real Data, Calibration, Final Integration, Release)  
**Data Bundle:** `data/processed/` (Real OpenStreetMap Bengaluru Network — Silk Board · BTM · Madiwala · HSR)

---

## 1. Network & Structural Integrity Validation

Both the CLI pipeline validator (`python -m urbanflow_data.cli validate`) and the Stage B7 validation harness (`bundle_integrity_checks`) were executed on the exported real Bengaluru bundle (`data/processed/`):

| # | Check | Result | Detail |
|---|-------|--------|--------|
| 1 | Required files present | **PASS** | All 10 required artifacts + `metro_stations.parquet` present |
| 2 | Graph is strongly connected | **PASS** | `1` strongly connected component (`220` nodes, `673` directed edges, `65.3 km`) |
| 3 | No zero or negative-length edges | **PASS** | `0` bad edges |
| 4 | No duplicate `edge_id`s | **PASS** | `673` unique `edge_id`s (`0..672`) |
| 5 | Positive lanes / speed / capacity / free-flow time | **PASS** | `0` invalid edges (`100%` positive) |
| 6 | Coordinate CRS is `EPSG:4326` inside study bbox | **PASS** | Bounding box `[12.910, 77.610] – [12.930, 77.630]` |
| 7 | Bus stops snapped within `max_snap_distance_m` (`50 m`) | **PASS** | `8/8` BMTC stops snapped (`1.5 m – 12.1 m`) |
| 8 | Bus route edge paths are contiguous | **PASS** | All `5` BMTC routes (`500D`, `356C`, `201R`, `25A`, `G3`, `94` route-edges) contiguous |
| 9 | BPR parameters cover every road class in graph | **PASS** | All `8` road classes covered (`trunk`, `primary`, `primary_link`, `secondary`, `tertiary`, `residential`, `living_street`, `busway`) |
| 10 | Reference congestion ratios within `[0.9, 7.0]` | **PASS** | Range `[1.000, 2.857]`, `0` outliers across `2,692` edge×slot rows |
| 11 | Copy-on-modify (`close_node`, `close_edge`, `add_edge`) leaves baseline unchanged | **PASS** | Verified immutable baseline graph |

---

## 2. Edge-Speed Agreement (BPR Simulation vs. Diurnal Reference Speeds)

Across `673` edges × `4` time slots (`2,692` edge×slot pairs), simulated BPR speeds (`TrafficSimulator.simulate()`) were compared against the reference edge speeds (`edge_speeds_by_slot.parquet`, source=`imputed_class_avg`):

### 2.1 Overall Edge-Speed Metrics
- **Sample count (`n`):** `2,692`
- **RMSE:** `6.35 km/h`
- **MAE:** `4.53 km/h`
- **MAPE:** `30.80%`
- **Bias (Simulated − Reference):** `+3.88 km/h`
- **Pearson Correlation ($r$):** `0.7163`

### 2.2 Breakdown by Time Slot

| Time Slot | `n` | RMSE (km/h) | MAE (km/h) | MAPE (%) | Bias (km/h) | Pearson $r$ |
|-----------|-----|-------------|------------|----------|-------------|-------------|
| `night_offpeak` | 673 | 1.22 | 0.50 | 1.62% | +0.50 | 0.9990 |
| `midday` | 673 | 5.38 | 4.37 | 24.99% | +4.33 | 0.9757 |
| `morning_peak` | 673 | 7.48 | 5.92 | 39.67% | +4.67 | 0.7658 |
| `evening_peak` | 673 | 8.65 | 7.33 | 56.93% | +6.02 | 0.7247 |

### 2.3 Breakdown by Highway Class

| Highway Class | `n` | RMSE (km/h) | MAE (km/h) | MAPE (%) | Bias (km/h) | Pearson $r$ |
|---------------|-----|-------------|------------|----------|-------------|-------------|
| `living_street` | 40 | 2.37 | 1.97 | 24.99% | +1.65 | 0.2010 |
| `residential` | 2,096 | 4.03 | 3.25 | 24.64% | +2.52 | 0.2259 |
| `busway` | 4 | 7.28 | 6.15 | 37.52% | +6.15 | — |
| `tertiary` | 232 | 7.47 | 6.12 | 41.71% | +5.47 | 0.4417 |
| `primary_link` | 12 | 9.14 | 8.16 | 62.01% | +2.64 | 0.6190 |
| `secondary` | 184 | 11.40 | 10.14 | 61.51% | +10.10 | 0.4294 |
| `trunk` | 60 | 16.22 | 14.60 | 50.72% | +14.60 | 0.4424 |
| `primary` | 64 | 17.89 | 16.05 | 83.43% | +16.05 | 0.1851 |

**Interpretation:** In `TrafficSimulator`, All-or-Nothing (AoN) shortest-path routing concentrates flow along minimum-free-flow-time collector paths while leaving peripheral parallel segments lightly loaded, yielding a positive mean speed bias (`+3.88 km/h`) relative to uniform road-class diurnal scaling while preserving strong rank correlation across slots ($r = 0.72\text{--}0.999$).

---

## 3. Corridor 70/30 Hold-Out Split & Honest Data Disclosure

- **Hold-out split mechanism:** Deterministic SHA-256 hash split (`holdout_fraction: 0.30`, `holdout_seed: 42`) implemented in `src/urbanflow_data/validation_harness.py` (`holdout_split()`) and wired into `src/urbanflow_data/calibrate.py` so that 30% of observed corridors in `config/sample_routes.csv` (`R01`–`R15`) are reserved strictly for out-of-sample testing and excluded from BPR $(\alpha, \beta)$ curve fitting.
- **Honest status of manual field observations:** No external API keys (`GOOGLE_MAPS_API_KEY`, `TOMTOM_API_KEY`, `HERE_API_KEY`) or field stopwatch CSVs (`data/raw/traffic/manual_observations_<name>.csv`) were supplied prior to release. Per project data-integrity rules, **no field observations or accuracy targets were fabricated**:
  - `validation.mape_target_pct` in `config/config.yaml` remains `null`.
  - Reference speeds in `data/processed/edge_speeds_by_slot.parquet` are explicitly tagged `source="imputed_class_avg"`.
  - The corridor hold-out pipeline is verified end-to-end by automated tests (`tests/test_b7_validation_harness.py`) and will automatically compute empirical hold-out MAPE as soon as `manual_observations_*.csv` files are dropped into `data/raw/traffic/`.

---

## 4. Machine-Learning Component Evaluation (`scripts/evaluate_ml.py`)

We evaluated `CongestionTrendPredictor` (Ridge regression on one-hot `time_slot` + `highway`) against two naive baselines on a deterministic **70/30 edge-level hold-out split** (`471` training edges / `1,884` rows vs. `202` hold-out test edges / `808` rows):

| Model / Baseline | Hold-Out RMSE | Hold-Out MAE | Hold-Out MAPE (%) | Decision |
|------------------|---------------|--------------|-------------------|----------|
| **`CongestionTrendPredictor` (Ridge ML)** | **0.1075** | **0.0684** | **4.69%** | **KEEP (`True`)** |
| Naive Road-Class Mean Baseline | 0.2603 | 0.2066 | 15.63% | Baseline |
| Naive Global Mean Baseline | 0.3184 | 0.2332 | 16.86% | Baseline |

- **Result:** `CongestionTrendPredictor` reduces hold-out RMSE by **58.7%** compared to the road-class mean baseline (`0.1075` vs. `0.2603`) and by **66.2%** compared to the global mean baseline (`0.1075` vs. `0.3184`), so it is retained as active in the decision layer.
- **`AnomalyDetector` (IsolationForest):** Trained on `12` multi-slot scenario simulation runs (`contamination=0.15`), flagging `2` extreme peak congestion scenarios (`model_available=True`).
