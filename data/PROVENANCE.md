# UrbanFlow Data & Network Modeling – Data Provenance Log
## Module 1 (Alent Varkey)

> Every dataset must be logged here with: source, download date, license, and any transformation applied.

---

## OSM Road Network

| Field | Value |
|-------|-------|
| Source | OpenStreetMap via OSMnx |
| URL | https://www.openstreetmap.org |
| License | Open Database License (ODbL) 1.0 |
| Attribution | Data (c) OpenStreetMap contributors, ODbL 1.0. https://osm.org/copyright |
| Download date | 2026-10-29 |
| Area | Silk Board – HSR Layout – Koramangala – BTM, Bengaluru |
| Transformations | graph simplification (osmnx), intersection consolidation (15 m tolerance), largest strongly connected component selected, lanes/maxspeed parsed & imputed |
| File | data/raw/osm_drive_raw.graphml |

---

## OSM Extra Features (signals, stops, POIs)

| Field | Value |
|-------|-------|
| Source | OpenStreetMap via OSMnx / Overpass API |
| License | ODbL 1.0 |
| Download date | 2026-10-29 |
| File | data/raw/osm_features.gpkg |

---

## BMTC Bus Routes / GTFS

| Field | Value |
|-------|-------|
| Source | *to be determined – check Mobility Database, OpenCity, DataMeet* |
| License | *to be verified* |
| Download date | 2026-10-29 |
| Notes | If GTFS unavailable, fallback is OSM public transport relations + manual CSV |
| Files | data/raw/gtfs/, data/interim/bus_routes.parquet, data/interim/bus_stops.parquet |

---

## Traffic Baseline

| Field | Value |
|-------|-------|
| Source | *to be determined – Google Maps / TomTom / HERE API, or manual sample* |
| License | See provider ToS |
| Download date | 2026-10-29 |
| Sampling | 30–60 key corridors, 4 time slots, 5 weekdays + 1 weekend |
| Cache | data/raw/traffic/ (all API responses cached with timestamp) |

---

*This file is updated automatically by the pipeline. Manual additions should be clearly marked.*
