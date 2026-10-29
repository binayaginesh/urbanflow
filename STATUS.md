# UrbanFlow Status

Update this file at the end of every stage. A stage may start only when the previous stage is DONE and its tag exists.

| Stage | Owner | State | Tag | Date done | Notes |
|---|---|---|---|---|---|
| 0 Phase closed (old code, first simulator and dashboard) | Binaya | DONE | phase0-closed | 2026-10-15 | Original author has left the project |
| A Engine upgrade + Decision AI | Mehrin | DONE | stage-a-done | 2026-10-27 | Branch: stage-a-decision (90/90 tests pass) |
| B Dashboard + Validation harness | Swathy | DONE | stage-b-done | 2026-10-28 | Branch: stage-b-platform (146 tests, 7 dashboard pages, Playwright suite) |
| C Real data + Release | Alent | DONE | v1.0 | 2026-10-29 | Branch: stage-c-release (220-node real Bengaluru OSM network, 11/11 validation checks, 147 tests pass) |

State values: NOT STARTED, IN PROGRESS, DONE, BLOCKED (needs X).

## Parallel human task (start now, no code)
Manual traffic observations (see docs/TEAM_PLAN.md Section 7.4). Each person adds their own file: `data/raw/traffic/manual_observations_<name>.csv`.

| Person | Routes/slots assigned | State |
|---|---|---|
| Binaya | R01–R04 | NOT PROVIDED (imputed_class_avg fallback used; documented in docs/VALIDATION.md) |
| Mehrin | R05–R08 | NOT PROVIDED (imputed_class_avg fallback used; documented in docs/VALIDATION.md) |
| Swathy | R09–R12 | NOT PROVIDED (imputed_class_avg fallback used; documented in docs/VALIDATION.md) |
| Alent | R13–R15 | NOT PROVIDED (imputed_class_avg fallback used; documented in docs/VALIDATION.md) |

## Hotfix log
(none)

## Open questions for the guide
(none)
