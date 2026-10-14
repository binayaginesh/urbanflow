# UrbanFlow Data Pipeline – Pipeline Documentation

## Overview

`
Raw OSM data         Raw traffic samples     GTFS / OSM transit
      |                       |                      |
      v                       v                      v
[Phase 1: Download + Clean]   [Phase 4: Baseline]   [Phase 3: Transit]
      |                       |                      |
      v                       v                      v
[Phase 2: Build Graph] -----> [Phase 4b: Calibrate] |
      |                                              |
      v                                              v
[Phase 5: Export] <------ [Merge all layers] <-------+
      |
      v
[Phase 5b: Validate] --> calibration_report.md
      |
      v
data/processed/  (handed to Member 2)
`

## Phases

### Phase 0 – Setup
- Create virtual environment: uv venv .venv && .venv\Scripts\activate
- Install dependencies: uv pip install -r requirements.txt
- Verify: python -m urbanflow_data.cli --help

### Phase 1 – Road Network (Steps 1 & 2)
1. **Download** (osm_download.py): fetches OSM drive graph + extra features via OSMnx; saves raw GraphML to data/raw/.
2. **Clean** (clean_network.py): keeps largest SCC, simplifies, consolidates intersections (15 m tolerance), parses and imputes lanes and maxspeed, adds *_imputed flags.

### Phase 2 – Graph Model (Step 3)
- **Build** (uild_graph.py): adds edge_id, computes ree_flow_speed_kmh, ree_flow_time_s, capacity_pcu_per_hr, flags, and exposes scenario API (close_edge, close_node, dd_edge).

### Phase 3 – Transit Layer (Step 4)
- **Transit** (	ransit.py): loads GTFS or OSM bus relations, clips to bbox, snaps stops to graph nodes, map-matches routes to edge paths, computes headways per slot.

### Phase 4 – Traffic Baseline & Calibration (Steps 5 & 6)
- **Baseline** (	raffic_baseline.py): samples travel times along key corridors from a traffic API (or manual CSV fallback); all responses cached to data/raw/traffic/.
- **Calibrate** (calibrate.py): distributes observed speeds to edges (length-weighted), imputes unsampled edges by class average, fits BPR α/β per road class by least-squares.

### Phase 5 – Export & Validation (Steps 7 & 8)
- **Export** (export.py): writes the full bundle to data/processed/ (see DATA_DICTIONARY for file list).
- **Validate** (alidate.py): runs automated correctness checks; reports RMSE/MAPE.

## One-Command Run

`ash
python -m urbanflow_data.cli run-all
# or for a quick debug with the small bbox:
python -m urbanflow_data.cli run-all --small --debug
`

## Individual Steps

`ash
python -m urbanflow_data.cli config-check
python -m urbanflow_data.cli download [--small]
python -m urbanflow_data.cli clean
python -m urbanflow_data.cli build-graph
python -m urbanflow_data.cli transit
python -m urbanflow_data.cli baseline
python -m urbanflow_data.cli calibrate
python -m urbanflow_data.cli export
python -m urbanflow_data.cli validate
`

## Reproducibility

Re-running with the same config.yaml and the same raw downloads must produce identical data/processed/ outputs. metadata.json records a SHA-256 of config.yaml so any config change is detectable.
