# UrbanFlow: AI-Powered Urban Mobility Decision Intelligence Platform for Bengaluru

> **Instructions to the AI coding agent (read this first)**
> You are helping build **Module 1 (Data & Network Modeling)** of a 4-person B.Tech Major Project.
> Everything above Section 6 is context. Section 6 onward is your task list.
> Rules:
> 1. Work phase by phase (Section 7). Finish and verify each phase before starting the next.
> 2. Never fabricate data. If a data source is unreachable or needs an API key, stop, write what is missing to `docs/BLOCKERS.md`, and continue with whatever is possible.
> 3. Ask the user before any step that costs money or needs a paid API key. Free tiers only by default.
> 4. Every dataset must have provenance: source, download date, license, and any transformation applied. Log it in `data/PROVENANCE.md`.
> 5. All tunable numbers (lanes, capacity, speeds, bounding box, time slots) live in `config/config.yaml`. No magic numbers in code.
> 6. Keep code modular, typed, and tested. The output contract in Section 8 must not be broken, because Member 2 depends on it.

---

## 1. Project Info

- **Institution:** Muthoot Institute of Technology and Science (Autonomous), Kochi
- **Department:** Artificial Intelligence and Data Science
- **Programme:** B.Tech in Computer Science and Engineering (AI), Major Project
- **Topic:** UrbanFlow, an AI-Powered Urban Mobility Decision Intelligence Platform for Bengaluru
- **Guide:** Mrs. Jincy Annie V V, Assistant Professor
- **Approved by:** Dr. Sumam Mary Idicula, Professor, Dept. of AI&DS

| Member | Name | Roll No | Module |
|---|---|---|---|
| 1 | Alent Varkey | MUT23CA012 | Data & Network Modeling (**this plan**) |
| 2 | Binaya Ginesh | MUT23CA027 | Simulation Engine |
| 3 | Mehrin Fathima M S | MUT23CA042 | Decision Intelligence / AI Layer |
| 4 | Swathy S Thankachi | MUT23CA068 | Platform, Integration & Validation |

## 2. Abstract

Bengaluru's rapid growth has made traffic congestion one of the city's biggest daily challenges, and decisions about new roads, flyovers, or event-related traffic diversions are often made without a clear way to know their real impact beforehand. Existing traffic simulation tools mostly show planners what might happen, but do not tell them what the best decision actually is. This project proposes UrbanFlow, an AI-powered platform that helps city planners test and evaluate transportation decisions before they are implemented. The system uses real road network data, past traffic patterns, and public transport information to build a working model of a chosen area in the city. Planners can enter a scenario, such as building a new road, closing a junction, or managing traffic for a VIP visit or public event, and the platform simulates how it would affect congestion, travel time, pollution, and bus delays. Instead of simply showing the outcome, the system compares different possible solutions and recommends the most effective one, based on which option reduces traffic the most while keeping cost and environmental impact low. The platform will be tested on real Bengaluru traffic data to compare predicted results with current traffic conditions. This project aims to move beyond simple traffic prediction and provide a practical, low-cost decision-support tool that helps city authorities plan smarter and reduce congestion effectively.

**Keywords:** Urban Traffic Planning, Traffic Simulation, Decision Support System, Artificial Intelligence, Smart City, Congestion Management, Bengaluru

## 3. Idea Summary

UrbanFlow lets a planner enter a scenario (new road, closed junction, VIP or event diversion), simulates the effect on congestion, travel time, bus delay and emissions, compares several candidate solutions, and recommends the best one with a human-readable justification.

## 4. System Architecture

```
[ Data & Network Layer ] -> [ Simulation Engine ] -> [ Decision Intelligence / AI ] -> [ Platform UI & Validation ]
      (Member 1)                (Member 2)                  (Member 3)                      (Member 4)
```

Integration flow:
1. Member 1's graph and data feed Member 2's simulator.
2. Member 2 runs each candidate scenario and outputs metrics.
3. Member 3 ranks scenarios and explains the top pick.
4. Member 4 wires everything into one app and validates against real traffic data.

## 5. Module Responsibilities (all members, for context)

- **Member 2 (Simulation):** takes `(network, scenario)` and returns `{congestion, travel_time, bus_delay, emissions}`. Uses SUMO or a custom NetworkX flow simulator.
- **Member 3 (AI layer):** MCDA scoring (weighted sum, TOPSIS), optional ML trend prediction, recommendation text.
- **Member 4 (Platform):** Streamlit or React dashboard, FastAPI backend, validation report.

---

## 6. YOUR TASK: Module 1, Data & Network Modeling (Alent Varkey)

**Goal:** Turn raw Bengaluru city data into a clean, calibrated, queryable road-network graph that the simulation engine can consume directly.

**What this module must deliver**
1. A cleaned road network dataset for a chosen Bengaluru study area (junctions, segments, lanes, speed limits, lengths).
2. A graph object where nodes are junctions and edges are road segments with capacity, length and free-flow speed.
3. Public transport layer: BMTC bus routes, stops and schedules (and Namma Metro if feasible), snapped onto the graph.
4. A baseline traffic layer: observed speeds and congestion by time of day, used to calibrate the model.
5. A reproducible pipeline: raw data -> cleaned data -> graph object, runnable with one command.
6. Documentation: pipeline docs, data dictionary, provenance, limitations.

**Tech stack:** Python 3.11+, OSMnx, NetworkX, pandas, GeoPandas, Shapely, pyproj, gtfs-kit (or partridge), PyYAML, pytest, matplotlib, folium (for quick map checks), pyarrow.

### 6.1 Study area decision

Do not model all of Bengaluru. Use a bounded area so simulation stays tractable (target 2,000 to 15,000 edges).

**Recommended primary area: Silk Board - HSR Layout - Koramangala - BTM corridor** (approx. 6 km x 6 km). Reasons: famously congested, has strong BMTC presence, has Namma Metro Yellow Line and nearby metro stations, and is a natural candidate for flyover, junction-closure and event scenarios.

**Alternates (switch via config):** Whitefield (ITPL corridor), Hebbal - Manyata Tech Park, Indiranagar - MG Road CBD.

Make the area a config setting (`study_area.bbox` as north, south, east, west, or `study_area.place_name`), so the same pipeline works for any area. Start with a small test area (about 1.5 km square) to debug, then scale up.

### 6.2 Repository layout

```
urbanflow-data/
  config/
    config.yaml                 # bbox, defaults, time slots, API toggles
  data/
    raw/                        # untouched downloads (osm, gtfs, traffic samples)
    interim/                    # cleaned intermediate files
    processed/                  # final graph + tables handed to Member 2
    PROVENANCE.md
  src/urbanflow_data/
    __init__.py
    config.py                   # loads and validates config.yaml
    osm_download.py             # Step 1
    clean_network.py            # Step 2
    build_graph.py              # Step 3
    transit.py                  # Step 4
    traffic_baseline.py         # Step 5
    calibrate.py                # Step 6
    export.py                   # Step 7
    validate.py                 # Step 8
    cli.py                      # `python -m urbanflow_data.cli run-all`
  notebooks/
    01_explore_network.ipynb
    02_check_traffic_baseline.ipynb
  tests/
  docs/
    DATA_DICTIONARY.md
    PIPELINE.md
    LIMITATIONS.md
    BLOCKERS.md
  requirements.txt
  README.md
```

---

## 7. Implementation Plan (phases and steps)

### Phase 0: Setup (about 0.5 day)
1. Create the repo layout above, a virtual environment, and `requirements.txt`.
2. Write `config/config.yaml` with: study area, CRS (use EPSG:4326 for storage and EPSG:32643 for metric calculations, since Bengaluru is in UTM zone 43N), default lanes, default speeds, default capacity per lane, PCU factors, time slots, and flags for optional API use.
3. Implement `config.py` to load and validate the config (fail loudly on missing keys).
4. Set up logging and a `Makefile` or CLI entry point.

**Done when:** `python -m urbanflow_data.cli --help` works and config loads.

### Phase 1: Road network acquisition and cleaning (about 2 days)

**Step 1: Download (`osm_download.py`)**
- Use OSMnx: `ox.graph_from_bbox(...)` with `network_type="drive"`, `simplify=False` first, so raw topology is preserved; save the raw graph as GraphML in `data/raw/`.
- Also download extra OSM features for context and save as GeoPackage:
  - Traffic signals, stop signs, crossings (`highway=traffic_signals`, etc.)
  - Bus stops (`highway=bus_stop`, `public_transport=platform`)
  - Metro stations (`railway=station` with `station=subway`)
  - Flyover and bridge flags (`bridge=yes`, `layer>0`)
  - POIs useful for events: stadiums, convention centres, malls, major hospitals, government buildings, tech parks
- Record the OSM download date in `PROVENANCE.md`. OSM license is ODbL, so add attribution "Data (c) OpenStreetMap contributors".

**Step 2: Clean (`clean_network.py`)**
- Keep the largest strongly connected component; log how many nodes and edges were dropped.
- Simplify the graph (`ox.simplify_graph`) and consolidate intersections (`ox.consolidate_intersections`, tolerance about 15 m) so one real junction is one node. Make tolerance configurable.
- Parse messy OSM tags into clean numeric columns:
  - `lanes`: can be string, list or missing. Take the max of lists, cast to int, impute by road class using config defaults.
  - `maxspeed`: strip " km/h", handle lists and missing values, impute by road class.
  - `oneway`, `length` (metres), `highway` (if list, take the highest-order class), `name`, `bridge`, `tunnel`.
- Add imputation flags (`lanes_imputed`, `speed_imputed`) so Members 2 and 3 know which values are assumptions.
- Report percent imputed per attribute. If imputation exceeds about 60% for lanes, flag it in `LIMITATIONS.md`.

**Done when:** a cleaned graph loads in a notebook, a folium map of it looks right, and a printed summary shows node count, edge count, total km, and the highway class distribution.

### Phase 2: Graph model with capacity attributes (about 1.5 days)

**Step 3: Build the simulation-ready graph (`build_graph.py`)**

Every edge must carry:
| Attribute | Meaning |
|---|---|
| `edge_id` | stable unique integer |
| `u`, `v` | node ids |
| `length_m` | segment length |
| `lanes` | integer lanes |
| `highway` | road class |
| `maxspeed_kmh` | posted or imputed speed limit |
| `free_flow_speed_kmh` | speed under no congestion (see below) |
| `free_flow_time_s` | `length_m / (free_flow_speed_kmh / 3.6)` |
| `capacity_pcu_per_hr` | `lanes * capacity_per_lane[highway]` |
| `is_bridge`, `is_flyover` | flags |
| `has_signal_at_v` | signal at the downstream node |
| `geometry` | LineString |

Node attributes: `node_id`, `x`, `y`, `degree`, `is_signalised`, `is_junction`.

Rules:
- `free_flow_speed_kmh = min(maxspeed_kmh, config.road_class_cap[highway])`. Indian urban roads rarely sustain posted limits, so allow a config reduction factor, and let calibration (Phase 4) override it with observed off-peak speeds.
- `capacity_per_lane` defaults in PCU per hour per lane, all in config. Starting values for Indian urban mixed traffic: trunk 1600, primary 1500, secondary 1300, tertiary 1000, residential 700. Add a "mixed traffic and friction" reduction multiplier for roads without separate lanes. Document that these are assumptions based on IRC:106 style guidance and must be cited and refined.
- Provide a PCU table (car 1.0, two-wheeler 0.5, auto-rickshaw 0.8, bus 3.0, truck 3.0 as starting values, all configurable) because Bengaluru traffic is dominated by two-wheelers. Member 2 will use this for emissions and flow.
- Build a helper API: `get_graph()`, `get_edge(edge_id)`, `neighbors(node)`, `shortest_path(a, b, weight)`, `edges_in_polygon(polygon)`, `nearest_node(lat, lon)`, `nearest_edge(lat, lon)`. These are what scenario injection (add road, close junction) will call, so make them fast and tested.
- Add scenario-friendly operations: `close_edge(edge_id)` and `close_node(node_id)` that return a **copy** of the graph (never mutate the baseline), and `add_edge(u, v, attrs)`.

**Done when:** unit tests pass for the helper API and for the copy-on-modify behaviour.

### Phase 3: Public transport layer (about 2 days)

**Step 4: Transit (`transit.py`)**
Goal: bus routes with stops and scheduled headways, mapped to graph edges, so Member 2 can compute **bus delay**.

Sources, in order of preference (verify availability and licensing before use, and record in PROVENANCE.md):
1. **BMTC GTFS feed.** Check open data portals and transit data catalogues (for example the Mobility Database, OpenCity, and DataMeet, plus any Bengaluru open transit data programme). If a GTFS zip exists, use it.
2. **OSM public transport relations** (`route=bus` relations) via OSMnx or the Overpass API, as a fallback for route geometry and stops.
3. **Manual curation.** For the chosen study area, hand-pick the 10 to 20 busiest BMTC routes (using the BMTC website or app route listings) and record route number, stop sequence, and peak and off-peak headway in a CSV. Mark clearly as "manually collected".

Tasks:
- Load GTFS with gtfs-kit: `routes`, `trips`, `stops`, `stop_times`, `shapes`, `frequencies` (if present).
- Clip to the study area bounding box.
- Snap each stop to the nearest graph node or edge (use a max snap distance in config, for example 50 m, and log failures).
- Map-match each route's shape or stop sequence to a path on the graph, producing `route_edges` (ordered list of edge_ids per route).
- Compute scheduled headway and scheduled running time per route and per time slot.
- Include Namma Metro stations and lines as a separate layer (stations, line geometry, approximate headway). Metro is **not** on the road graph, but station locations matter for event scenarios and for mode context.
- Output tables: `bus_routes.parquet`, `bus_stops.parquet`, `bus_route_edges.parquet`, `metro_stations.parquet`.

**Done when:** a map shows bus routes overlaid on the road graph, every route has a contiguous edge path (log any that fail), and stop-snap statistics are reported.

### Phase 4: Baseline traffic data and calibration (about 3 days)

This is the most important data step, because the project promises validation against real traffic.

**Step 5: Collect observed traffic (`traffic_baseline.py`)**

Strategy: you cannot get per-edge live speeds for free everywhere, so sample **travel times along key corridors and origin-destination pairs** and map them back to the graph.

1. Choose 30 to 60 **sampling routes** inside the study area: major corridors (for example Silk Board to HSR BDA Complex, Koramangala 80 Feet Road, Outer Ring Road segments, Hosur Road segments) plus several cross-area OD pairs. Store them in `config/sample_routes.csv` with origin and destination coordinates.
2. Choose **time slots** (config): night off-peak (23:00), morning peak (08:00 to 10:00), midday (13:00 to 15:00), evening peak (17:30 to 20:00). Sample across 5 weekdays and 1 weekend.
3. Pull travel times (with and without traffic) from **one** provider's free tier. Options, check current free limits and terms of service before use:
   - Google Maps Routes API or Distance Matrix API (`duration` vs `duration_in_traffic`)
   - TomTom Routing or Traffic Flow API
   - HERE Routing or Traffic API
   Ask the user which API key they have. Cache every response to `data/raw/traffic/` with timestamp so nothing is ever requested twice.
4. **Fallback if no API key or quota:**
   - Use any public Bengaluru traffic dataset found on Kaggle or open data portals (search "Bangalore traffic dataset"; check license and what the columns actually contain before relying on it). Datasets of this kind often give area-level congestion indices over time rather than per-road speeds, so use them for **temporal shape** (hourly congestion profile) and not for per-edge speeds.
   - Or manual logging: record travel times for 15 to 20 key corridors from the Google Maps app for the same time slots, into a CSV with columns `route_id, datetime, travel_time_s, free_flow_time_s, source`. Be honest in the documentation that this is a small manual sample.
5. For each sampled route, compute `congestion_ratio = observed_time / free_flow_time` and `observed_speed_kmh`.

**Step 6: Calibrate (`calibrate.py`)**
- Map-match each sampled route to graph edges.
- Distribute the observed route speed onto its edges (length-weighted), producing `observed_speed[edge, time_slot]` for sampled edges.
- For unsampled edges, impute using the average `congestion_ratio` of the same road class and time slot, with a documented fallback.
- Replace `free_flow_speed_kmh` with the off-peak observed speed where available (cap at the posted limit).
- Fit **BPR (Bureau of Public Roads) volume-delay parameters** per road class: `t = t0 * (1 + alpha * (v/c)^beta)`. Start with alpha 0.15 and beta 4, then tune alpha and beta per class so that predicted peak speeds match observed ones (simple least squares or grid search). Save as `bpr_params.json`.
- Produce a **baseline demand estimate** (stretch goal, coordinate with Member 2): a gravity-model or grid-zone origin-destination matrix scaled so a baseline run reproduces the observed peak congestion ratios. If skipped, document that Member 2 must supply demand.
- Output: `edge_speeds_by_slot.parquet` (edge_id, time_slot, speed_kmh, congestion_ratio, source: observed or imputed), `bpr_params.json`, a calibration report with RMSE and MAPE of speeds.

**Done when:** a calibration report exists with error metrics, plots of observed vs modelled speed, and a clear statement of what fraction of edges are observed vs imputed.

### Phase 5: Export, validation and documentation (about 2 days)

**Step 7: Export (`export.py`)**
Write the final bundle to `data/processed/` (see Section 8 for the exact contract):
- `network.graphml` (NetworkX graph with all attributes)
- `edges.parquet` and `nodes.parquet` (flat tables) plus `network.gpkg` (GeoPackage for GIS and the dashboard map)
- `bus_*.parquet`, `metro_stations.parquet`
- `edge_speeds_by_slot.parquet`, `bpr_params.json`
- `pois.gpkg` (event-relevant places)
- `metadata.json`: study area, build date, OSM extract date, counts, config hash, version

**Step 8: Validate (`validate.py`)** and tests
Automated checks, all must pass:
- Graph is strongly connected; no zero-length or negative-length edges; no duplicate edge ids.
- All edges have positive lanes, speed, capacity, free-flow time.
- Free-flow speed never exceeds the posted limit plus tolerance.
- Every bus route edge path is connected on the graph.
- Congestion ratios are within a sane range (about 1.0 to 6.0); flag outliers.
- Re-running the pipeline with the same config yields identical outputs (determinism).
- Copy-on-modify scenario helpers do not change the baseline graph.

**Step 9: Documentation**
- `README.md`: install, config, run commands, expected runtime.
- `docs/DATA_DICTIONARY.md`: every column in every output file.
- `docs/PIPELINE.md`: diagram and explanation of the flow.
- `docs/LIMITATIONS.md`: honest list (OSM tag gaps, imputed lanes, sampled traffic only, two-wheeler heterogeneity, no signal timing data, time-of-day coverage, API terms).
- A short **handoff note for Member 2** describing how to load the graph and call the helper API, with a 10-line code example.

---

## 8. Output Contract (do not break; Member 2 depends on this)

```python
from urbanflow_data import load_network

net = load_network("data/processed")   # returns NetworkBundle

net.graph            # networkx.MultiDiGraph, edges carry attributes in the table above
net.edges            # GeoDataFrame, one row per edge
net.nodes            # GeoDataFrame, one row per node
net.bus_routes       # DataFrame
net.bus_route_edges  # DataFrame: route_id, seq, edge_id
net.edge_speeds      # DataFrame: edge_id, time_slot, speed_kmh, congestion_ratio, source
net.bpr_params       # dict by road class
net.meta             # dict

net.close_edge(edge_id) -> NetworkBundle         # returns a modified copy
net.close_node(node_id) -> NetworkBundle
net.add_edge(u, v, **attrs) -> NetworkBundle
net.edges_in_polygon(shapely_polygon) -> list[int]
net.nearest_node(lat, lon) -> int
```

Keep these names and types stable. If a change is unavoidable, bump `metadata.json` version and note it in the handoff doc.

## 9. Suggested Timeline (about 11 working days of effort)

| Phase | Focus | Effort |
|---|---|---|
| 0 | Setup, config | 0.5 d |
| 1 | OSM download and cleaning | 2 d |
| 2 | Graph model, helper API | 1.5 d |
| 3 | Bus and metro layer | 2 d |
| 4 | Traffic baseline and calibration | 3 d |
| 5 | Export, validation, docs | 2 d |

Priority if time is short: Phase 0, 1, 2 first (Member 2 can start once these are done), then Phase 4 with the fallback data, then Phase 3.

## 10. Acceptance Checklist

- [ ] One command rebuilds everything from raw data
- [ ] Study area graph with at least 2,000 edges, all attributes populated, imputation flagged
- [ ] Bus routes mapped on graph with stated coverage
- [ ] Baseline speeds by time slot with a calibration report (RMSE and MAPE)
- [ ] BPR parameters fitted per road class
- [ ] Output contract implemented and tested
- [ ] PROVENANCE, DATA_DICTIONARY, PIPELINE, LIMITATIONS written
- [ ] Handoff note delivered to Member 2

## 11. Useful Code Starters (for the agent to adapt)

```python
# osm_download.py
import osmnx as ox
G = ox.graph_from_bbox(bbox=(west, south, east, north), network_type="drive", simplify=False)
ox.save_graphml(G, "data/raw/osm_drive_raw.graphml")
```

```python
# clean_network.py (outline)
G = ox.simplify_graph(G)
G = ox.consolidate_intersections(ox.project_graph(G, to_crs="EPSG:32643"),
                                 tolerance=15, rebuild_graph=True, dead_ends=False)
nodes, edges = ox.graph_to_gdfs(G)
# parse lanes/maxspeed -> numeric, impute by highway class from config, add *_imputed flags
```

```python
# BPR
def bpr_time(t0, volume, capacity, alpha=0.15, beta=4.0):
    return t0 * (1 + alpha * (volume / capacity) ** beta)
```
