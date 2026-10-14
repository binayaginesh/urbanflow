# Data Dictionary

Column definitions for every output file produced by the pipeline.

---

## edges.parquet / network.graphml (edge attributes)

| Column | Type | Description |
|--------|------|-------------|
| edge_id | int | Stable unique integer identifier per directed edge |
| u | int | Source node id |
| v | int | Target node id |
| length_m | float | Segment length in metres |
| lanes | int | Number of lanes (parsed or imputed) |
| lanes_imputed | bool | True if lanes value was imputed from road class default |
| highway | str | OSM highway tag (highest-order class if list) |
| maxspeed_kmh | float | Posted speed limit (km/h); parsed or imputed |
| speed_imputed | bool | True if maxspeed_kmh was imputed |
| free_flow_speed_kmh | float | min(maxspeed_kmh, class_cap) * reduction_factor |
| free_flow_time_s | float | length_m / (free_flow_speed_kmh / 3.6) |
| capacity_pcu_per_hr | float | lanes * capacity_per_lane * capacity_reduction_factor |
| is_bridge | bool | True if OSM bridge=yes |
| is_flyover | bool | True if bridge=yes and layer > 0 |
| has_signal_at_v | bool | True if the downstream node has a traffic signal |
| name | str | Road name from OSM |
| oneway | bool | True if one-way road |
| geometry | LineString | WGS-84 geometry |

## nodes.parquet (node attributes)

| Column | Type | Description |
|--------|------|-------------|
| node_id | int | OSMnx node id |
| x | float | Longitude (WGS-84) |
| y | float | Latitude (WGS-84) |
| degree | int | Graph degree |
| is_signalised | bool | True if OSM highway=traffic_signals |
| is_junction | bool | True if degree >= 3 |
| geometry | Point | WGS-84 point |

## bus_routes.parquet

| Column | Type | Description |
|--------|------|-------------|
| route_id | str | GTFS or manual route identifier |
| route_short_name | str | Bus route number (e.g. "500C") |
| route_long_name | str | Descriptive name |
| agency | str | Operator (BMTC) |
| peak_headway_min | float | Average headway during morning/evening peak |
| offpeak_headway_min | float | Average headway off-peak |
| source | str | "gtfs" / "osm_relation" / "manual" |

## bus_stops.parquet

| Column | Type | Description |
|--------|------|-------------|
| stop_id | str | GTFS or OSM stop identifier |
| stop_name | str | Stop name |
| lat | float | Latitude |
| lon | float | Longitude |
| snapped_node | int | Nearest graph node id (within snap distance) |
| snap_distance_m | float | Distance to snapped node |
| snap_ok | bool | True if snap_distance_m <= max_snap_distance_m |

## bus_route_edges.parquet

| Column | Type | Description |
|--------|------|-------------|
| route_id | str | Bus route identifier |
| seq | int | Sequence number of edge in route path |
| edge_id | int | Graph edge traversed |

## edge_speeds_by_slot.parquet

| Column | Type | Description |
|--------|------|-------------|
| edge_id | int | Graph edge |
| time_slot | str | One of the configured slot names |
| speed_kmh | float | Observed or imputed speed |
| congestion_ratio | float | observed_time / free_flow_time |
| source | str | "observed" / "imputed_class_avg" / "imputed_fallback" |

## bpr_params.json

JSON object keyed by road class string. Each value is {alpha: float, beta: float}.

## metadata.json

| Field | Description |
|-------|-------------|
| version | Pipeline version string |
| build_date | ISO-8601 build timestamp |
| osm_extract_date | Date OSM data was downloaded |
| study_area | Bounding box dict |
| node_count | Number of graph nodes |
| edge_count | Number of graph edges |
| total_length_km | Sum of edge lengths in km |
| config_hash | SHA-256 of config.yaml for reproducibility |
