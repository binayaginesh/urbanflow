# Antigravity Prompts (one per person)

How to use: open Antigravity, start a new session, paste **your** prompt below, and press go. The agent clones the repo (if needed), reads the plan, checks that the previous stage is finished, and then works step by step. If the agent asks which stage you are, answer with your letter.

Repo: https://github.com/binayaginesh/urbanflow.git
Order of work: Binaya (push files) then Mehrin (A) then Swathy (B) then Alent (C).

---

## Binaya: push the plan files (do this first, once)

```
I need to prepare the UrbanFlow repo for my team. 
1. Clone https://github.com/binayaginesh/urbanflow.git if it is not already open (or use the open folder).
2. Create these files from the attachments I give you: docs/TEAM_PLAN.md (the team plan), STATUS.md at the repo root, and docs/ANTIGRAVITY_PROMPTS.md.
3. Do not change any other file.
4. Commit with the message "docs: add team plan, status and prompts", push to main, then create and push the tag phase0-closed.
5. Show me the git log and confirm the tag exists on the remote.
Do not force push or rewrite history. Ask me before anything destructive.
```
Then on GitHub: Settings, Collaborators, add Mehrin, Swathy and Alent with write access, and send them the repo link plus their prompt.

---

## Mehrin: Stage A (Engine upgrade + Decision Intelligence and AI)

```
Clone https://github.com/binayaginesh/urbanflow.git (or use the open folder), then read docs/TEAM_PLAN.md completely, then STATUS.md.

I am Mehrin and I own Stage A. Follow Section 0 of the plan exactly: confirm in STATUS.md that stage 0 is DONE and the tag phase0-closed exists, create the branch stage-a-decision, set up a Python 3.10 or 3.11 virtual environment, install requirements, install the package with pip install -e src/, and run pytest.

Your job is Stage A (Sections 4 and 5 of the plan), in this order:
A1 repo setup and scripts,
A2 upgrade the simulation engine so closures reroute traffic and new roads attract flow (the current simulator has no demand or routing, which is why every scenario gets NOT RECOMMENDED),
A3 the decision layer: criteria and scoring, the three-tier verdict (RECOMMENDED, MODERATE, NOT RECOMMENDED), TOPSIS ranking, Monte Carlo confidence, explanations, the optimizer that suggests the top 3 interventions, and the ML components,
A4 definition of done, handoff note docs/HANDOFF_A.md, merge to main, tag stage-a-done, update STATUS.md.

Rules: plan first and show me the plan, then work one numbered step at a time; run pytest after each step; commit after each step with the prefix "stage-a:"; never invent data, costs or accuracy numbers; never hard-code a verdict; no LLM may compute or change numbers; do not start Stage B or C work; never force push or delete history. Ask me if a requirement is unclear.
```

---

## Swathy: Stage B (Dashboard, visible simulation, validation harness)

```
Clone https://github.com/binayaginesh/urbanflow.git (or use the open folder), then read docs/TEAM_PLAN.md completely, then STATUS.md and docs/HANDOFF_A.md.

I am Swathy and I own Stage B. First check STATUS.md: Stage A must be DONE and the tag stage-a-done must exist (git tag). If not, stop and tell me to wait for Mehrin. Then follow Section 0: git pull, create the branch stage-b-platform, set up a Python 3.10 or 3.11 virtual environment, install requirements, pip install -e src/, run pytest and python scripts/demo_check.py.

Your job is Stage B (Section 6 of the plan): build the dark command-center dashboard (demo/app.py with pages) using the real engine and verdict APIs from Stage A: Command Center, Scenario Lab with before/after maps, a change (delta) map, animated vehicle flow and heatmap, a verdict card with traffic-light colours, confidence and a waterfall chart, Compare and Recommend (with "AI suggests"), AI Insights, Transit and Metro, Validation (harness), Pipeline and Data; plus the PDF planner report, offline mode (no internet, no map tiles), demo cache mode, Playwright smoke tests with screenshots, and make everything read data only from the URBANFLOW_DATA_DIR setting. Finish with the Stage B definition of done, docs/HANDOFF_B.md, merge to main, tag stage-b-done, update STATUS.md.

Rules: plan first and show me the plan, then one numbered step at a time; pytest after each step; commit with the prefix "stage-b:"; no invented data; do not start Stage C work; never force push or delete history. Ask me if anything is unclear.
```

---

## Alent: Stage C (Real data, calibration, final integration, release)

```
Clone https://github.com/binayaginesh/urbanflow.git (or use the open folder), then read docs/TEAM_PLAN.md completely, then STATUS.md, docs/HANDOFF_A.md and docs/HANDOFF_B.md.

I am Alent and I own Stage C. First check STATUS.md: Stage B must be DONE and the tag stage-b-done must exist. If not, stop and tell me to wait for Swathy. Then follow Section 0: git pull, create the branch stage-c-release, set up a Python 3.10 or 3.11 virtual environment, install requirements, pip install -e src/, run pytest and python scripts/demo_check.py. I have internet access on this machine.

Your job is Stage C (Section 7 of the plan): run the real Bengaluru data pipeline (small area first, then the full area), apply manual road overrides, build the bus and metro layers, load and calibrate with the manual traffic observations in data/raw/traffic/ with a 70/30 hold-out split, fit BPR parameters, add events, VIP routes, costs and demand zones, switch the dashboard to real data with URBANFLOW_DATA_DIR=data/processed, run python scripts/run_library.py and recalibrate the verdict thresholds with python scripts/calibrate_thresholds.py, run the ML scripts on real observations (keep a model only if it beats the baseline), run validation on the hold-out corridors and write docs/VALIDATION.md honestly, finish all docs, and cut the release: merge to main, tag v1.0, write docs/HANDOFF_C.md, update STATUS.md.

Rules: plan first and show me the plan, then one numbered step at a time; pytest after each step; commit with the prefix "stage-c:"; never fabricate data, costs or citations (if a value is unknown leave it null and tell me); if a verdict tier is missing on real data, change the scenario design with reasoning, never hard-code or force thresholds; do not commit API keys or large raw files; never force push or delete history. Ask me if anything is unclear.
```
