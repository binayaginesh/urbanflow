"""
traffic_baseline.py - Phase 4a
Collect observed travel times along key corridors.
Falls back to manual CSV if no API key configured.
"""
from __future__ import annotations
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def run(cfg: dict[str, Any], root: Path = Path("."), **kwargs) -> None:
    import pandas as pd

    interim_dir = root / cfg["paths"]["interim_dir"]
    cache_dir   = root / cfg["traffic_baseline"]["cache_dir"]
    cache_dir.mkdir(parents=True, exist_ok=True)

    sample_routes_path = root / cfg["traffic_baseline"]["sample_routes_csv"]
    api_provider       = cfg["traffic_baseline"].get("api_provider")

    # Load or create sample routes
    if not sample_routes_path.exists():
        logger.warning("sample_routes.csv not found at %s. Creating template.", sample_routes_path)
        _create_sample_routes_template(sample_routes_path, cfg)
        logger.info("Created template at %s -- fill in the CSV and re-run.", sample_routes_path)
        return

    routes_df = pd.read_csv(sample_routes_path)
    logger.info("Loaded %d sample routes from %s", len(routes_df), sample_routes_path)

    if api_provider and api_provider != "null":
        results = _fetch_from_api(routes_df, cfg, cache_dir)
    else:
        results = _load_manual_fallback(routes_df, cache_dir, interim_dir)

    if results is not None and len(results) > 0:
        out = interim_dir / "traffic_raw.parquet"
        results.to_parquet(out, index=False)
        logger.info("Traffic baseline raw data saved: %d records -> %s", len(results), out)
    else:
        logger.warning("No traffic baseline data collected. Calibration will use fallback imputation.")


def _create_sample_routes_template(path: Path, cfg: dict) -> None:
    """Write a template sample_routes.csv for the Silk Board–BTM corridor."""
    import pandas as pd
    rows = [
        # (route_id, name, orig_lat, orig_lon, dest_lat, dest_lon)
        ("R01","Silk Board to HSR BDA Complex",       12.9172,77.6233, 12.9116,77.6413),
        ("R02","HSR Layout to Koramangala 80ft Rd",   12.9116,77.6413, 12.9352,77.6245),
        ("R03","Koramangala to BTM Layout",            12.9352,77.6245, 12.9182,77.6103),
        ("R04","BTM to Silk Board via Hosur Rd",       12.9182,77.6103, 12.9172,77.6233),
        ("R05","ORR Silk Board to Marathahalli (stub)", 12.9172,77.6233, 12.9560,77.7010),
        ("R06","Koramangala 80ft to St Johns Hospital",12.9352,77.6245, 12.9356,77.6017),
        ("R07","HSR Sector 1 to Agara Junction",       12.9070,77.6380, 12.9210,77.6390),
        ("R08","BTM 2nd Stage to NIMHANS circle",      12.9090,77.6070, 12.9413,77.5965),
        ("R09","Koramangala Forum Mall to Ejipura",    12.9348,77.6170, 12.9500,77.6218),
        ("R10","Silk Board to Electronic City Phase 1",12.9172,77.6233, 12.8455,77.6754),
    ]
    df = pd.DataFrame(rows, columns=["route_id","route_name","orig_lat","orig_lon","dest_lat","dest_lon"])
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def _fetch_from_api(routes_df, cfg: dict, cache_dir: Path):
    """Fetch travel times from the configured API provider."""
    import os, pandas as pd
    provider = cfg["traffic_baseline"]["api_provider"]
    api_cfg  = cfg["api"]

    if provider == "google":
        key = os.environ.get(api_cfg["google_api_key_env"])
        if not key:
            logger.error("Set env var %s before running with api_provider=google", api_cfg["google_api_key_env"])
            return None
        return _fetch_google(routes_df, key, cache_dir)
    elif provider == "tomtom":
        key = os.environ.get(api_cfg["tomtom_api_key_env"])
        if not key:
            logger.error("Set env var %s before running with api_provider=tomtom", api_cfg["tomtom_api_key_env"])
            return None
        return _fetch_tomtom(routes_df, key, cache_dir)
    else:
        logger.warning("Unknown api_provider '%s'. Falling back to manual CSV.", provider)
        return None


def _fetch_google(routes_df, api_key: str, cache_dir: Path):
    """Call Google Routes/Distance Matrix API (free tier) and cache responses."""
    import requests, pandas as pd
    rows = []
    for slot in [("morning_peak","08:00","09:00"), ("evening_peak","17:30","18:30"),
                  ("midday","13:00","14:00"), ("night_offpeak","23:00","00:00")]:
        slot_name, hour_start, _ = slot
        for _, r in routes_df.iterrows():
            cache_file = cache_dir / f"google_{r['route_id']}_{slot_name}.json"
            if cache_file.exists():
                data = json.loads(cache_file.read_text())
                logger.debug("Cache hit: %s", cache_file.name)
            else:
                url = "https://maps.googleapis.com/maps/api/distancematrix/json"
                params = {
                    "origins":      f"{r['orig_lat']},{r['orig_lon']}",
                    "destinations": f"{r['dest_lat']},{r['dest_lon']}",
                    "departure_time": "now",
                    "traffic_model":  "best_guess",
                    "key":            api_key,
                }
                try:
                    resp = requests.get(url, params=params, timeout=10)
                    data = resp.json()
                    cache_file.write_text(json.dumps(data, indent=2))
                    time.sleep(0.1)
                except Exception as e:
                    logger.warning("API call failed for %s: %s", r["route_id"], e)
                    continue

            try:
                elem = data["rows"][0]["elements"][0]
                free_flow_s = elem["duration"]["value"]
                in_traffic_s = elem.get("duration_in_traffic", {}).get("value", free_flow_s)
                rows.append({
                    "route_id": r["route_id"], "time_slot": slot_name,
                    "datetime": datetime.now().isoformat(),
                    "free_flow_time_s": free_flow_s,
                    "observed_time_s": in_traffic_s,
                    "congestion_ratio": round(in_traffic_s / max(free_flow_s, 1), 3),
                    "source": "google_api",
                })
            except Exception as e:
                logger.debug("Parse error for %s: %s", r["route_id"], e)

    return pd.DataFrame(rows) if rows else None


def _fetch_tomtom(routes_df, api_key: str, cache_dir: Path):
    """Call TomTom Routing API and cache responses."""
    import requests, pandas as pd
    rows = []
    for _, r in routes_df.iterrows():
        cache_file = cache_dir / f"tomtom_{r['route_id']}.json"
        if cache_file.exists():
            data = json.loads(cache_file.read_text())
        else:
            url = (f"https://api.tomtom.com/routing/1/calculateRoute/"
                   f"{r['orig_lat']},{r['orig_lon']}:{r['dest_lat']},{r['dest_lon']}/json")
            params = {"key": api_key, "traffic": "true", "travelMode": "car"}
            try:
                resp = requests.get(url, params=params, timeout=10)
                data = resp.json()
                cache_file.write_text(json.dumps(data, indent=2))
                time.sleep(0.1)
            except Exception as e:
                logger.warning("TomTom call failed for %s: %s", r["route_id"], e)
                continue

        try:
            leg = data["routes"][0]["legs"][0]["summary"]
            rows.append({
                "route_id": r["route_id"], "time_slot": "realtime",
                "datetime": datetime.now().isoformat(),
                "free_flow_time_s": leg.get("historicTrafficTravelTimeInSeconds", leg["travelTimeInSeconds"]),
                "observed_time_s": leg["travelTimeInSeconds"],
                "congestion_ratio": round(leg["travelTimeInSeconds"] / max(leg.get("historicTrafficTravelTimeInSeconds",1),1), 3),
                "source": "tomtom_api",
            })
        except Exception as e:
            logger.debug("Parse error for %s: %s", r["route_id"], e)

    return pd.DataFrame(rows) if rows else None


def _load_manual_fallback(routes_df, cache_dir: Path, interim_dir: Path):
    """
    Look for manually collected traffic CSV in cache_dir.
    Expected columns: route_id, time_slot, datetime, free_flow_time_s, observed_time_s, source
    """
    import pandas as pd
    manual_file = cache_dir / "manual_traffic.csv"
    if manual_file.exists():
        df = pd.read_csv(manual_file)
        df["congestion_ratio"] = df["observed_time_s"] / df["free_flow_time_s"].clip(lower=1)
        logger.info("Loaded manual traffic data: %d records from %s", len(df), manual_file)
        return df
    else:
        logger.warning("No manual traffic CSV found at %s. Creating template.", manual_file)
        template = pd.DataFrame(columns=["route_id","time_slot","datetime",
                                          "free_flow_time_s","observed_time_s","source"])
        template.to_csv(manual_file, index=False)
        logger.info("Created empty template: %s -- fill this in and re-run.", manual_file)
        return None
