# Blockers

This file is updated whenever the pipeline cannot proceed due to a missing API key,
unreachable data source, or policy constraint.

## Open Blockers

## BLOCKER 1: Public Overpass API Rate-Limiting on Full 6x6 km BBox
- **Date detected:** 2026-10-29
- **Description:** Public Overpass API mirrors (`overpass-api.de`, `overpass.kumi.systems`, `overpass.private.coffee`) returned `403 Forbidden` / `502 Bad Gateway` / read timeouts when querying the full 6 km x 6 km bounding box, after succeeding on the Silk Board – BTM – HSR study bounding box (`903 raw nodes, 1,849 raw edges -> 220 consolidated junctions, 673 directed edges, 65.3 km`).
- **What is needed:** Either a local Overpass instance or an off-peak retry window when `overpass-api.de` lifts rate-limiting.
- **Workaround applied:** Retained the real OpenStreetMap Silk Board corridor extract (`data/raw/osm_drive_raw.graphml`, 220 consolidated nodes, 673 edges, 65.3 km) downloaded on 2026-10-29.

## BLOCKER 2: BMTC GTFS Feed
- **Date detected:** 2026-10-29
- **Description:** No official open BMTC GTFS zip file is present at `transit.gtfs_zip_path`.
- **What is needed:** A valid BMTC GTFS zip archive from OpenCity / Mobility Database / BMTC.
- **Workaround applied:** Using OpenStreetMap `route=bus` relations and curated Silk Board corridor BMTC routes snapped to the real OSM graph (`transit.py`).

## BLOCKER 3: Live Traffic API Key & Field Manual Observation CSVs
- **Date detected:** 2026-10-29
- **Description:** `GOOGLE_MAPS_API_KEY` / `TOMTOM_API_KEY` are not configured (`api.use_traffic_api: false`), and human team members have not yet committed `data/raw/traffic/manual_observations_<name>.csv` (`STATUS.md` lists manual observations as `NOT STARTED`).
- **What is needed:** Either team members' manual corridor observation CSVs in `data/raw/traffic/` or a free-tier Google/TomTom API key.
- **Workaround applied:** Calibration (`calibrate.py`) uses road-class diurnal congestion profiles and documents 0% field-observed coverage honestly in `docs/VALIDATION.md` and `docs/calibration_report.md` without fabricating observations.

---

## Resolved Blockers

*None yet.*

---

*Format: one section per blocker – date, description, what is needed, workaround applied.*
