# Limitations

Honest list of known data gaps and modelling assumptions.

| # | Limitation | Impact | Mitigation |
|---|-----------|--------|------------|
| 1 | OSM lane tags are missing for many residential/service roads (~40–70%) | Capacity estimates for these roads rely on config defaults | Imputation flag lanes_imputed added; document in DATA_DICTIONARY |
| 2 | maxspeed tags absent or inconsistent on many roads | Free-flow speed is imputed by road class | speed_imputed flag; calibration with observed speeds overrides |
| 3 | No per-cycle signal timing data available from BBMP | BPR model cannot model intersection delay explicitly | Use aggregate capacity reduction factor; note in handoff |
| 4 | Bengaluru traffic is highly heterogeneous (dominant two-wheelers) | Standard HCM capacity tables may overestimate capacity | PCU conversion table applied; factor configurable |
| 5 | Traffic baseline is based on sampled corridors only (not every edge) | Unsampled edges get class-average congestion ratios | source column distinguishes observed vs imputed |
| 6 | BMTC GTFS feed availability uncertain | Bus layer may fall back to manual / OSM relation data | Blocker logged in BLOCKERS.md if GTFS unavailable |
| 7 | No night-time traffic counts; night off-peak assumed from road-class ratios | Night calibration less accurate | Clearly flagged in calibration report |
| 8 | Model covers road network only; pedestrian/cycling modes excluded | Does not capture mode-shift effects | Scope limitation accepted |

*This file is updated as new limitations are discovered during the pipeline.*
