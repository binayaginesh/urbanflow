"""
validation_harness.py - Stage B7: model validation harness.

Three independent checks, all computed from files in the data directory:

1. Edge-speed agreement: simulated edge speeds vs the speeds stored in
   ``edge_speeds_by_slot.parquet`` (RMSE, MAE, MAPE, bias, Pearson r), per slot
   and per road class. The ``source`` column of that table is propagated so the
   UI can say clearly whether the reference is observed, imputed or synthetic.
2. Corridor hold-out validation: manual traffic observations
   (``data/raw/traffic/manual_observations_*.csv`` and ``manual_traffic.csv``)
   are matched to ``config/sample_routes.csv`` corridors, split deterministically
   into calibration / hold-out sets, and compared to the simulated corridor
   congestion ratio.
3. Bundle integrity checks on the loaded NetworkBundle.

No accuracy number is invented. When inputs are missing the harness returns
empty tables and says so; pass/fail on accuracy is only reported if a target is
set in ``config.yaml`` (``validation.mape_target_pct``).
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import networkx as nx
import numpy as np
import pandas as pd

from urbanflow_data.network_bundle import NetworkBundle
from urbanflow_data.simulation_engine import SimResult
from urbanflow_data.transit_analysis import haversine_m

# Sources that count as real measurements (anything else is labelled as such).
OBSERVED_SOURCES: frozenset[str] = frozenset({"observed", "api", "manual", "google", "tomtom", "here"})

MANUAL_REQUIRED = ("route_id", "datetime", "free_flow_time_s")
MANUAL_TIME_COLS = ("travel_time_s", "observed_time_s")


# ── Metrics ───────────────────────────────────────────────────────────────────
def error_metrics(observed: pd.Series | np.ndarray, predicted: pd.Series | np.ndarray) -> dict[str, float | int | None]:
    """RMSE, MAE, MAPE (%), bias (pred - obs) and Pearson r. None when undefined."""
    o = np.asarray(observed, dtype=float)
    p = np.asarray(predicted, dtype=float)
    mask = np.isfinite(o) & np.isfinite(p)
    o, p = o[mask], p[mask]
    n = int(len(o))
    if n == 0:
        return {"n": 0, "rmse": None, "mae": None, "mape_pct": None, "bias": None, "pearson_r": None}
    err = p - o
    nz = o != 0
    mape = float(np.mean(np.abs(err[nz] / o[nz])) * 100.0) if nz.any() else None
    r = None
    if n >= 3 and np.std(o) > 0 and np.std(p) > 0:
        r = float(np.corrcoef(o, p)[0, 1])
    return {
        "n": n,
        "rmse": float(np.sqrt(np.mean(err ** 2))),
        "mae": float(np.mean(np.abs(err))),
        "mape_pct": mape,
        "bias": float(np.mean(err)),
        "pearson_r": r,
    }


def metrics_by(df: pd.DataFrame, key: str, obs_col: str, pred_col: str) -> pd.DataFrame:
    """Error metrics grouped by *key*."""
    rows = []
    for k, g in df.groupby(key, sort=True):
        rows.append({key: k, **error_metrics(g[obs_col], g[pred_col])})
    return pd.DataFrame(rows)


def reference_label(sources: pd.Series) -> str:
    """Human label for the reference data: 'observed', 'synthetic', 'imputed' or 'mixed'."""
    vals = {str(s).lower() for s in sources.dropna().unique()}
    if not vals:
        return "unknown"
    if vals <= OBSERVED_SOURCES:
        return "observed"
    if all("synthetic" in v for v in vals):
        return "synthetic"
    if vals == {"imputed"}:
        return "imputed"
    return "mixed"


# ── 1. Edge-speed agreement ───────────────────────────────────────────────────
def compare_edge_speeds(net: NetworkBundle, sims_by_slot: dict[str, SimResult]) -> pd.DataFrame:
    """Join reference edge speeds with simulated speeds for each slot in *sims_by_slot*."""
    cols = ["edge_id", "time_slot", "highway", "observed_speed_kmh", "simulated_speed_kmh",
            "error_kmh", "abs_pct_error", "source"]
    ref = net.edge_speeds
    if ref is None or ref.empty:
        return pd.DataFrame(columns=cols)
    hw = net.edges[["edge_id", "highway"]]
    rows = []
    for slot, res in sims_by_slot.items():
        part = ref[ref["time_slot"] == slot]
        for _, r in part.iterrows():
            eid = int(r["edge_id"])
            if eid not in res.edge_speeds:
                continue
            obs = float(r["speed_kmh"])
            simv = float(res.edge_speeds[eid])
            rows.append({
                "edge_id": eid, "time_slot": slot,
                "observed_speed_kmh": obs, "simulated_speed_kmh": simv,
                "error_kmh": simv - obs,
                "abs_pct_error": abs(simv - obs) / obs * 100.0 if obs else None,
                "source": r.get("source", "unknown"),
            })
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=cols)
    df = df.merge(hw, on="edge_id", how="left")
    return df[cols]


# ── 2. Corridor hold-out ──────────────────────────────────────────────────────
def holdout_split(ids: list[str], test_fraction: float, seed: int) -> tuple[list[str], list[str]]:
    """
    Deterministic calibration / hold-out split by corridor id.

    Each id is ranked by sha1(f"{seed}:{id}"); the last ``round(n * test_fraction)``
    ids form the hold-out set. Same inputs always give the same split, and adding
    a new corridor does not reshuffle existing ones' relative order.
    """
    uniq = sorted(set(str(i) for i in ids))
    if not uniq:
        return [], []
    ranked = sorted(uniq, key=lambda i: hashlib.sha1(f"{seed}:{i}".encode()).hexdigest())
    n_test = int(round(len(ranked) * test_fraction))
    if 0 < test_fraction < 1 and len(ranked) >= 2:
        n_test = min(max(n_test, 1), len(ranked) - 1)
    return sorted(ranked[: len(ranked) - n_test]), sorted(ranked[len(ranked) - n_test:])


def assign_time_slot(ts: pd.Timestamp, slots: list[dict[str, Any]]) -> str | None:
    """Map a timestamp to the configured slot with the nearest centre (circular clock distance)."""
    if ts is None or pd.isna(ts) or not slots:
        return None
    minutes = ts.hour * 60 + ts.minute
    best, best_d = None, math.inf
    for s in slots:
        c = int(s["hour"]) * 60 + int(s.get("minute", 0))
        d = abs(minutes - c)
        d = min(d, 1440 - d)
        if d < best_d:
            best, best_d = s["name"], d
    return best


def load_manual_observations(traffic_dir: str | Path, slots: list[dict[str, Any]]) -> pd.DataFrame:
    """
    Load every manual observation CSV in *traffic_dir*.

    Accepts ``manual_observations_*.csv`` (team plan schema: route_id, datetime,
    travel_time_s, free_flow_time_s, source) and ``manual_traffic.csv``
    (pipeline schema: observed_time_s, optional time_slot). Rows with missing or
    non-positive times are dropped. Returns columns: route_id, datetime,
    time_slot, travel_time_s, free_flow_time_s, congestion_ratio, source, file.
    """
    cols = ["route_id", "datetime", "time_slot", "travel_time_s", "free_flow_time_s",
            "congestion_ratio", "source", "file"]
    d = Path(traffic_dir)
    if not d.exists():
        return pd.DataFrame(columns=cols)
    files = sorted(d.glob("manual_observations_*.csv")) + sorted(d.glob("manual_traffic.csv"))
    frames = []
    for f in files:
        try:
            df = pd.read_csv(f)
        except Exception:
            continue
        if df.empty or any(c not in df.columns for c in MANUAL_REQUIRED):
            continue
        tcol = next((c for c in MANUAL_TIME_COLS if c in df.columns), None)
        if tcol is None:
            continue
        out = pd.DataFrame({
            "route_id": df["route_id"].astype(str),
            "datetime": pd.to_datetime(df["datetime"], errors="coerce"),
            "travel_time_s": pd.to_numeric(df[tcol], errors="coerce"),
            "free_flow_time_s": pd.to_numeric(df["free_flow_time_s"], errors="coerce"),
            "source": df["source"].astype(str) if "source" in df.columns else "manual",
            "file": f.name,
        })
        if "time_slot" in df.columns:
            out["time_slot"] = df["time_slot"].where(df["time_slot"].notna(), None)
        else:
            out["time_slot"] = None
        frames.append(out)
    if not frames:
        return pd.DataFrame(columns=cols)
    obs = pd.concat(frames, ignore_index=True)
    obs = obs[(obs["travel_time_s"] > 0) & (obs["free_flow_time_s"] > 0)].copy()
    missing_slot = obs["time_slot"].isna()
    obs.loc[missing_slot, "time_slot"] = obs.loc[missing_slot, "datetime"].apply(lambda t: assign_time_slot(t, slots))
    obs["congestion_ratio"] = obs["travel_time_s"] / obs["free_flow_time_s"]
    return obs[cols].reset_index(drop=True)


def _nearest_node(net: NetworkBundle, lat: float, lon: float) -> tuple[int, float]:
    best = (None, math.inf)
    for _, n in net.nodes.iterrows():
        d = haversine_m(lat, lon, float(n["y"]), float(n["x"]))
        if d < best[1]:
            best = (int(n["node_id"]), d)
    return best  # type: ignore[return-value]


def simulated_corridor_ratio(G: nx.MultiDiGraph, sim: SimResult, o: int, d: int) -> float | None:
    """Simulated travel time / free-flow time along the free-flow shortest path o→d."""
    if o == d or o not in G or d not in G:
        return None
    try:
        path = nx.shortest_path(G, o, d, weight="free_flow_time_s")
    except nx.NetworkXNoPath:
        return None
    ff_t = sim_t = 0.0
    for a, b in zip(path[:-1], path[1:]):
        data = min(G[a][b].values(), key=lambda e: float(e.get("free_flow_time_s", math.inf)))
        lm = float(data.get("length_m", 0))
        ff = float(data.get("free_flow_time_s", 0))
        spd = float(sim.edge_speeds.get(int(data.get("edge_id", -1)), data.get("free_flow_speed_kmh", 30)))
        ff_t += ff
        sim_t += lm / (spd / 3.6) if spd > 0 else math.inf
    return sim_t / ff_t if ff_t > 0 else None


def corridor_validation(
    net: NetworkBundle,
    sims_by_slot: dict[str, SimResult],
    observations: pd.DataFrame,
    sample_routes: pd.DataFrame,
    holdout_fraction: float,
    seed: int,
    max_snap_m: float,
) -> pd.DataFrame:
    """
    Per (corridor, slot): mean observed congestion ratio vs simulated corridor
    ratio, labelled 'calibration' or 'holdout'.
    """
    cols = ["route_id", "route_name", "time_slot", "n_obs", "observed_ratio", "simulated_ratio",
            "error", "split", "snap_m"]
    if observations.empty or sample_routes is None or sample_routes.empty:
        return pd.DataFrame(columns=cols)
    routes = sample_routes.set_index(sample_routes["route_id"].astype(str))
    obs = observations[observations["route_id"].isin(routes.index)]
    if obs.empty:
        return pd.DataFrame(columns=cols)
    _, test_ids = holdout_split(obs["route_id"].unique().tolist(), holdout_fraction, seed)
    test_set = set(test_ids)

    rows = []
    for (rid, slot), g in obs.groupby(["route_id", "time_slot"]):
        if slot not in sims_by_slot:
            continue
        r = routes.loc[rid]
        o, so = _nearest_node(net, float(r["orig_lat"]), float(r["orig_lon"]))
        d, sd = _nearest_node(net, float(r["dest_lat"]), float(r["dest_lon"]))
        snap = max(so, sd)
        sim_ratio = simulated_corridor_ratio(net.graph, sims_by_slot[slot], o, d) if snap <= max_snap_m else None
        obs_ratio = float(g["congestion_ratio"].mean())
        rows.append({
            "route_id": rid, "route_name": r.get("route_name", rid), "time_slot": slot,
            "n_obs": int(len(g)), "observed_ratio": round(obs_ratio, 3),
            "simulated_ratio": round(sim_ratio, 3) if sim_ratio is not None else None,
            "error": round(sim_ratio - obs_ratio, 3) if sim_ratio is not None else None,
            "split": "holdout" if rid in test_set else "calibration",
            "snap_m": round(snap, 0),
        })
    return pd.DataFrame(rows, columns=cols)


# ── 3. Bundle integrity ───────────────────────────────────────────────────────
def bundle_integrity_checks(net: NetworkBundle, ratio_range: tuple[float, float]) -> list[dict[str, Any]]:
    """Structural checks on the loaded bundle (no osmnx needed)."""
    G = net.graph
    out: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        out.append({"check": name, "passed": bool(ok), "detail": detail})

    n_scc = nx.number_strongly_connected_components(G) if G.number_of_nodes() else 0
    add("Graph is strongly connected", n_scc == 1, f"{n_scc} component(s)")

    bad_len = sum(1 for _, _, d in G.edges(data=True) if float(d.get("length_m", 0)) <= 0)
    add("No zero/negative-length edges", bad_len == 0, f"{bad_len} bad edge(s)")

    eids = [d.get("edge_id") for _, _, d in G.edges(data=True)]
    dupes = len(eids) - len(set(eids))
    add("No duplicate edge_ids", dupes == 0, f"{dupes} duplicate(s)")

    bad_attr = sum(
        1 for _, _, d in G.edges(data=True)
        if any(float(d.get(k, 0)) <= 0 for k in ("lanes", "free_flow_speed_kmh", "capacity_pcu_per_hr", "free_flow_time_s"))
    )
    add("Positive lanes / speed / capacity / free-flow time", bad_attr == 0, f"{bad_attr} bad edge(s)")

    if net.edge_speeds is not None and not net.edge_speeds.empty:
        lo, hi = ratio_range
        cr = net.edge_speeds["congestion_ratio"]
        oor = int(((cr < lo) | (cr > hi)).sum())
        add(f"Reference congestion ratios within [{lo}, {hi}]", oor == 0, f"{oor} outlier(s)")

    if not net.bus_route_edges.empty:
        uv = net.edges.set_index("edge_id")[["u", "v"]]
        broken = []
        for rid, g in net.bus_route_edges.sort_values("seq").groupby("route_id"):
            seq = [int(e) for e in g["edge_id"] if int(e) in uv.index]
            for a, b in zip(seq[:-1], seq[1:]):
                if int(uv.loc[a, "v"]) != int(uv.loc[b, "u"]):
                    broken.append(str(rid))
                    break
        add("Bus route edge paths are contiguous", not broken, ", ".join(broken) if broken else "all routes contiguous")

    classes = {str(d.get("highway")) for _, _, d in G.edges(data=True)}
    missing = sorted(c for c in classes if c not in net.bpr_params or not {"alpha", "beta"} <= set(net.bpr_params[c]))
    add("BPR params cover every road class in graph", not missing, ", ".join(missing) or "complete")

    n_before = G.number_of_edges()
    some_node = next(iter(G.nodes), None)
    if some_node is not None:
        _ = net.close_node(some_node)
        add("Copy-on-modify leaves baseline unchanged", G.number_of_edges() == n_before and some_node in G)
    return out


# ── Aggregate report ──────────────────────────────────────────────────────────
@dataclass
class ValidationReport:
    reference_label: str
    edge_df: pd.DataFrame
    edge_overall: dict[str, Any]
    edge_by_slot: pd.DataFrame
    edge_by_class: pd.DataFrame
    corridor_df: pd.DataFrame
    holdout_metrics: dict[str, Any]
    calibration_metrics: dict[str, Any]
    n_manual_obs: int
    integrity: list[dict[str, Any]]
    mape_target_pct: float | None
    notes: list[str] = field(default_factory=list)

    @property
    def integrity_passed(self) -> bool:
        return all(c["passed"] for c in self.integrity)

    @property
    def holdout_meets_target(self) -> bool | None:
        """True/False only when a target is configured and hold-out data exists."""
        mape = self.holdout_metrics.get("mape_pct")
        if self.mape_target_pct is None or mape is None:
            return None
        return mape <= self.mape_target_pct


def run_validation(
    net: NetworkBundle,
    sims_by_slot: dict[str, SimResult],
    cfg: dict[str, Any],
    root: str | Path = ".",
) -> ValidationReport:
    """Run all three validation components and return a ValidationReport."""
    vcfg = cfg.get("validation", {}) or {}
    root = Path(root)
    holdout_fraction = float(vcfg.get("holdout_fraction", 0.30))
    seed = int(vcfg.get("holdout_seed", 42))
    ratio_range = tuple(vcfg.get("congestion_ratio_range", [0.9, 7.0]))
    target = vcfg.get("mape_target_pct")
    max_snap = float(cfg.get("transit", {}).get("max_snap_distance_m", 50))
    corridor_snap = float(vcfg.get("corridor_max_snap_m", max_snap))
    notes: list[str] = []

    edge_df = compare_edge_speeds(net, sims_by_slot)
    label = reference_label(edge_df["source"]) if not edge_df.empty else "unavailable"
    if label == "synthetic":
        notes.append("Reference edge speeds are SYNTHETIC demo values, not field observations. "
                     "Edge-speed agreement shows model consistency only and must not be reported as accuracy.")
    elif label == "unavailable":
        notes.append("No reference edge speeds found (edge_speeds_by_slot.parquet missing or empty).")

    traffic_dir = root / cfg.get("traffic_baseline", {}).get("cache_dir", "data/raw/traffic")
    obs = load_manual_observations(traffic_dir, cfg.get("time_slots", []))
    routes_csv = root / cfg.get("traffic_baseline", {}).get("sample_routes_csv", "config/sample_routes.csv")
    sample_routes = pd.read_csv(routes_csv) if routes_csv.exists() else pd.DataFrame()
    corr = corridor_validation(net, sims_by_slot, obs, sample_routes, holdout_fraction, seed, corridor_snap)
    if obs.empty:
        notes.append(f"No manual traffic observations found in {traffic_dir.as_posix()}/ — corridor hold-out "
                     "validation will run once Stage C adds manual_observations_<name>.csv files.")

    def _split_metrics(split: str) -> dict[str, Any]:
        part = corr[(corr["split"] == split) & corr["simulated_ratio"].notna()] if not corr.empty else corr
        return error_metrics(part["observed_ratio"], part["simulated_ratio"]) if not part.empty else error_metrics([], [])

    return ValidationReport(
        reference_label=label,
        edge_df=edge_df,
        edge_overall=error_metrics(edge_df["observed_speed_kmh"], edge_df["simulated_speed_kmh"]) if not edge_df.empty else error_metrics([], []),
        edge_by_slot=metrics_by(edge_df, "time_slot", "observed_speed_kmh", "simulated_speed_kmh") if not edge_df.empty else pd.DataFrame(),
        edge_by_class=metrics_by(edge_df, "highway", "observed_speed_kmh", "simulated_speed_kmh") if not edge_df.empty else pd.DataFrame(),
        corridor_df=corr,
        holdout_metrics=_split_metrics("holdout"),
        calibration_metrics=_split_metrics("calibration"),
        n_manual_obs=int(len(obs)),
        integrity=bundle_integrity_checks(net, ratio_range),
        mape_target_pct=float(target) if target is not None else None,
        notes=notes,
    )

