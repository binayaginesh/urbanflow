# Limitations

Honest list of known data gaps and modelling assumptions in UrbanFlow v1.0.

| # | Limitation | Impact | Mitigation |
|---|-----------|--------|------------|
| 1 | OSM lane tags are missing for 92.4% of edges (mostly residential/tertiary streets) | Capacity estimates for untagged edges rely on `config.yaml` defaults + manual corridor overrides | `lanes_imputed` boolean flag exported on every edge; 75 major arterial edges overridden in `road_overrides.corridors` |
| 2 | `maxspeed` tags are absent on 93.3% of OSM edges in the study area | Free-flow speed is imputed by road class + manual corridor overrides | `speed_imputed` boolean flag exported on every edge; documented in `docs/DATA_DICTIONARY.md` |
| 3 | No per-cycle signal timing plans available from BBMP / BTP | BPR volume-delay curves cannot model phase-by-phase intersection delay explicitly | `capacity_reduction_factor: 0.85` applied; 7 landmark signalised intersections explicitly annotated |
| 4 | Bengaluru traffic is highly heterogeneous (two-wheelers, autos, buses, cars) | Standard homogeneous capacity tables overestimate mixed-traffic discharge | Indian HCM PCU equivalents (`two_wheeler: 0.5`, `auto_rickshaw: 0.8`, `bus: 3.0`) configured in `config.yaml` |
| 5 | No live Traffic API key or field stopwatch CSVs supplied in `data/raw/traffic/` | Reference speeds in `edge_speeds_by_slot.parquet` use road-class diurnal profiles (`imputed_class_avg`); BPR $(\alpha, \beta)$ use literature defaults (`0.15, 4.0`) | Tagged transparently in `source` column and `docs/VALIDATION.md`; 70/30 hold-out harness ready for field CSV drop-in |
| 6 | Official BMTC GTFS zip not publicly released | Bus network covers 5 curated high-frequency Silk Board / BTM / Hosur Rd corridors (`500D`, `356C`, `201R`, `25A`, `G3`) rather than all city routes | Map-matched onto 94 contiguous real OSM edges with 8 snapped stops (`<= 12.1 m`) |
| 7 | Static All-or-Nothing (AoN) shortest-path flow assignment | Concentrates O–D flow onto minimum-free-flow-time paths rather than Wardrop user equilibrium (UE) | Path-hop demand scaling + BPR congestion feedback; single-source Dijkstra keeps simulation under 0.15s |
| 8 | Civil intervention monetary costs (`estimated_cost_inr_crore`) are `null` | TOPSIS uses relative `cost_index` (`0.0–1.0`) rather than INR Crore budgets | Left `null` intentionally to avoid fabricating DPR/BBMP/BMRCL financial figures |

> **Auto-flagged by `clean_network.py`:** Lane imputation is 92.4% (>60%). Capacity estimates for untagged minor streets rely on `config/config.yaml` defaults, while primary/trunk corridors (`Hosur Road`, `Outer Ring Road`, `Sarjapura Road`, `Mahayogi Vemana Road`, `Maruthi Nagar Main Road`, `16th Main Road`) use verified corridor overrides.
