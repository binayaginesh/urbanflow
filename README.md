# UrbanFlow – Data & Network Modeling (Module 1)

**Part of:** UrbanFlow – AI-Powered Urban Mobility Decision Intelligence Platform for Bengaluru  
**Team Member:** Alent Varkey (MUT23CA012)

---

## What This Module Does

Transforms raw OpenStreetMap data and observed traffic samples into a clean, calibrated, queryable road-network graph that the simulation engine (Module 2, Binaya Ginesh) can consume directly.

**Output contract:** rom urbanflow_data import load_network

---

## Quick Start

`ash
# 1. Clone and enter the repo
git clone https://github.com/binayaginesh/urbanflow.git
cd urbanflow

# 2. Create virtual environment (Python 3.11)
uv venv .venv --python 3.11
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux / macOS

# 3. Install dependencies
uv pip install -r requirements.txt
pip install -e src/             # installs the urbanflow_data package

# 4. Check config
python -m urbanflow_data.cli config-check

# 5. Run full pipeline (debug run on small bbox, no API key needed)
python -m urbanflow_data.cli run-all --small

# 6. Run tests
pytest tests/ -v
`

---

## Configuration

All tunable numbers live in [config/config.yaml](config/config.yaml).  
Key settings:

| Setting | Default | Description |
|---------|---------|-------------|
| study_area.bbox | Silk Board–HSR–Koramangala–BTM | Primary 6 km × 6 km corridor |
| study_area.small_bbox | ~1.5 km square | Debug area (use --small flag) |
| crs.storage | EPSG:4326 | WGS-84 for all stored files |
| crs.metric | EPSG:32643 | UTM Zone 43N for length/area calculations |
| pr_defaults.alpha | 0.15 | BPR delay model alpha |
| pr_defaults.beta | 4.0 | BPR delay model beta |
| pi.use_traffic_api | false | Set true and add env var to enable traffic API |

To switch study area, change study_area.place_name or study_area.bbox in config.yaml.

---

## Repository Layout

`
urbanflow/
  config/
    config.yaml           ← all tunable parameters
    sample_routes.csv     ← traffic sampling corridors (Phase 4)
  data/
    raw/                  ← untouched downloads (never modify)
    interim/              ← cleaned intermediate files
    processed/            ← final outputs consumed by Module 2
    PROVENANCE.md         ← data lineage log
  src/urbanflow_data/     ← Python package
    config.py             ← config loader / validator
    osm_download.py       ← Phase 1 Step 1
    clean_network.py      ← Phase 1 Step 2
    build_graph.py        ← Phase 2
    transit.py            ← Phase 3
    traffic_baseline.py   ← Phase 4a
    calibrate.py          ← Phase 4b
    export.py             ← Phase 5a
    validate.py           ← Phase 5b
    network_bundle.py     ← NetworkBundle dataclass + load_network()
    cli.py                ← CLI entry point
  tests/
  docs/
    DATA_DICTIONARY.md
    PIPELINE.md
    LIMITATIONS.md
    BLOCKERS.md
  requirements.txt
`

---

## Output Files (data/processed/)

| File | Format | Description |
|------|--------|-------------|
| network.graphml | GraphML | Full NetworkX MultiDiGraph |
| edges.parquet | Parquet | Edge table with all attributes |
| nodes.parquet | Parquet | Node table |
| network.gpkg | GeoPackage | GIS-ready combined layer |
| bus_routes.parquet | Parquet | BMTC route metadata |
| bus_stops.parquet | Parquet | Stop locations + snap info |
| bus_route_edges.parquet | Parquet | route_id, seq, edge_id |
| metro_stations.parquet | Parquet | Namma Metro station layer |
| edge_speeds_by_slot.parquet | Parquet | Speed/congestion by time slot |
| bpr_params.json | JSON | BPR α/β per road class |
| metadata.json | JSON | Build info, counts, config hash |

---

## Docs

- [Pipeline overview](docs/PIPELINE.md)
- [Data dictionary](docs/DATA_DICTIONARY.md)
- [Limitations](docs/LIMITATIONS.md)
- [Blockers](docs/BLOCKERS.md)
- [Provenance](data/PROVENANCE.md)

---

## License

Code: MIT. Data: see [data/PROVENANCE.md](data/PROVENANCE.md) for per-dataset licenses.
