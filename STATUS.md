# UrbanFlow Status

Update this file at the end of every stage. A stage may start only when the previous stage is DONE and its tag exists.

| Stage | Owner | State | Tag | Date done | Notes |
|---|---|---|---|---|---|
| 0 Phase closed (old code, first simulator and dashboard) | Binaya | DONE | phase0-closed | 2026-10-15 | Original author has left the project |
| A Engine upgrade + Decision AI | Mehrin | DONE | stage-a-done | 2026-10-27 | Branch: stage-a-decision (90/90 tests pass) |
| B Dashboard + Validation harness | Swathy | DONE | stage-b-done | 2026-10-28 | Branch: stage-b-platform (146 tests, 7 dashboard pages, Playwright suite) |
| C Real data + Release | Alent | NOT STARTED | v1.0 | | Branch: stage-c-release |

State values: NOT STARTED, IN PROGRESS, DONE, BLOCKED (needs X).

## Parallel human task (start now, no code)
Manual traffic observations (see docs/TEAM_PLAN.md Section 7.4). Each person adds their own file: `data/raw/traffic/manual_observations_<name>.csv`.

| Person | Routes/slots assigned | State |
|---|---|---|
| Binaya | | NOT STARTED |
| Mehrin | | NOT STARTED |
| Swathy | | NOT STARTED |
| Alent | | NOT STARTED |

## Hotfix log
(none)

## Open questions for the guide
(none)
