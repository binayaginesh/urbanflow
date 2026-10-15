"""
demo/generate_demo_data.py
Generates a realistic synthetic Bengaluru road network for demo purposes.
No internet needed. Creates data/processed/ ready for the dashboard.
"""
import json, math, random, sys
from pathlib import Path

import networkx as nx
import pandas as pd
import geopandas as gpd
from shapely.geometry import LineString, Point

random.seed(42)

# ── Real Bengaluru study-area junctions (lat, lon, name) ────────────────────
NODES = [
    (0,  12.9172, 77.6233, "Silk Board Junction"),
    (1,  12.9116, 77.6413, "HSR BDA Complex"),
    (2,  12.9352, 77.6245, "Koramangala 80 ft Rd"),
    (3,  12.9182, 77.6103, "BTM Layout Signal"),
    (4,  12.9050, 77.6300, "Agara Lake Junction"),
    (5,  12.9210, 77.6390, "Agara Junction"),
    (6,  12.9420, 77.6170, "Koramangala Forum"),
    (7,  12.9290, 77.6050, "JP Nagar Flyover"),
    (8,  12.9500, 77.6100, "Jayanagar 4th Block"),
    (9,  12.9340, 77.6380, "Sony World Junction"),
    (10, 12.9130, 77.6550, "HSR Sector 6"),
    (11, 12.9000, 77.6450, "Haralur Road"),
    (12, 12.9600, 77.6300, "Lalbagh West Gate"),
    (13, 12.9080, 77.6190, "BTM 2nd Stage"),
    (14, 12.9430, 77.6320, "Ejipura Signal"),
    (15, 12.9230, 77.6200, "HSR 27th Main"),
]

# ── Road segments (u, v, highway, lanes, length_m, name) ────────────────────
EDGES_DEF = [
    (0, 1,  "primary",   2, 2100, "Outer Ring Road"),
    (1, 5,  "secondary", 2, 1200, "HSR Layout Main"),
    (5, 9,  "secondary", 2,  900, "Agara to Sony World"),
    (9, 2,  "primary",   2,  800, "Koramangala 80ft Road"),
    (2, 6,  "secondary", 2,  600, "Koramangala Inner"),
    (6, 14, "secondary", 2,  700, "Ejipura Road"),
    (14,12, "tertiary",  1,  900, "Lalbagh Connect"),
    (12, 8, "secondary", 2,  800, "Jayanagar Road"),
    (8,  7, "secondary", 2,  700, "JP Nagar Link"),
    (7,  3, "primary",   2, 1100, "BTM Main Road"),
    (3,  0, "primary",   2, 1500, "Hosur Road"),
    (3, 13, "tertiary",  1,  500, "BTM 2nd Stage Road"),
    (13, 0, "secondary", 2,  900, "BTM to Silk Board"),
    (0,  4, "secondary", 2,  800, "Agara Lake Road"),
    (4,  5, "secondary", 2,  700, "Agara Connector"),
    (4, 15, "tertiary",  1,  600, "HSR 27th Main"),
    (15, 1, "secondary", 2,  800, "HSR Layout Inner"),
    (1, 10, "secondary", 2, 1000, "HSR Sector 6 Road"),
    (10,11, "tertiary",  1,  900, "Haralur Road"),
    (11, 4, "tertiary",  1,  800, "Haralur Connect"),
    (2,  9, "secondary", 2,  500, "Sony World Link"),
    (6, 12, "tertiary",  1,  900, "Forum to Lalbagh"),
    # reverse directions (bidirectional roads)
    (1, 0,  "primary",   2, 2100, "Outer Ring Road"),
    (5, 1,  "secondary", 2, 1200, "HSR Layout Main"),
    (9, 5,  "secondary", 2,  900, "Sony World to Agara"),
    (2, 9,  "primary",   2,  800, "Koramangala 80ft Road"),
    (6, 2,  "secondary", 2,  600, "Koramangala Inner"),
    (3, 7,  "secondary", 2,  700, "JP Nagar Link"),
    (0, 3,  "primary",   2, 1500, "Hosur Road"),
    (5, 4,  "secondary", 2,  700, "Agara Connector"),
]

CAPACITY = {"motorway":1800,"trunk":1600,"primary":1500,"secondary":1300,"tertiary":1000,"residential":700,"unclassified":900}
FREE_FLOW = {"motorway":70,"trunk":55,"primary":45,"secondary":35,"tertiary":28,"residential":20,"unclassified":28}

CONGESTION = {
    "night_offpeak":  {"primary":1.05,"secondary":1.05,"tertiary":1.0},
    "morning_peak":   {"primary":2.8, "secondary":2.5,"tertiary":1.9},
    "midday":         {"primary":1.6, "secondary":1.5,"tertiary":1.3},
    "evening_peak":   {"primary":3.1, "secondary":2.8,"tertiary":2.1},
}

BUS_ROUTES = [
    {"route_id":"500C","route_short_name":"500C","route_long_name":"Silk Board to Kempegowda Bus Station",
     "agency":"BMTC","peak_headway_min":5,"offpeak_headway_min":12,"source":"manual",
     "edge_path":[0,1,5,9,2]},
    {"route_id":"201R","route_short_name":"201R","route_long_name":"BTM Layout to MG Road",
     "agency":"BMTC","peak_headway_min":8,"offpeak_headway_min":20,"source":"manual",
     "edge_path":[3,0,1,5]},
    {"route_id":"356E","route_short_name":"356E","route_long_name":"Koramangala to Majestic",
     "agency":"BMTC","peak_headway_min":10,"offpeak_headway_min":25,"source":"manual",
     "edge_path":[2,6,14,12,8]},
    {"route_id":"G11","route_short_name":"G11","route_long_name":"HSR Layout Circular",
     "agency":"BMTC","peak_headway_min":15,"offpeak_headway_min":30,"source":"manual",
     "edge_path":[1,10,11,4,5,1]},
]

METRO_STATIONS = [
    {"name":"Silk Board Metro","lat":12.9172,"lon":77.6233,"line":"Yellow"},
    {"name":"HSR Layout Metro","lat":12.9116,"lon":77.6413,"line":"Yellow"},
    {"name":"Agara Metro",     "lat":12.9050,"lon":77.6300,"line":"Yellow"},
    {"name":"BTM Layout Metro","lat":12.9182,"lon":77.6103,"line":"Yellow"},
]

def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def build(out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    node_map = {n[0]: n for n in NODES}  # id -> (id, lat, lon, name)

    G = nx.MultiDiGraph()
    for nid, lat, lon, name in NODES:
        G.add_node(nid, y=lat, x=lon, name=name,
                   node_id=nid, is_signalised=(nid in {0,2,3,6,9}),
                   is_junction=True, degree=3)

    edge_id = 0
    edges_rows = []
    for u, v, hw, lanes, length_m, name in EDGES_DEF:
        ulat, ulon = node_map[u][1], node_map[u][2]
        vlat, vlon = node_map[v][1], node_map[v][2]
        geom = LineString([(ulon, ulat), (vlon, vlat)])
        ff   = FREE_FLOW.get(hw, 30) * 0.9
        fft  = length_m / (ff / 3.6)
        cap  = lanes * CAPACITY.get(hw, 1000) * 0.85
        attrs = dict(edge_id=edge_id, length_m=length_m, lanes=lanes,
                     highway=hw, maxspeed_kmh=FREE_FLOW.get(hw,30),
                     free_flow_speed_kmh=round(ff,2),
                     free_flow_time_s=round(fft,2),
                     capacity_pcu_per_hr=round(cap,1),
                     is_bridge=False, is_flyover=False,
                     has_signal_at_v=(v in {0,2,3,6,9}),
                     name=name, lanes_imputed=False, speed_imputed=False,
                     geometry=geom)
        G.add_edge(u, v, **attrs)
        edges_rows.append({"edge_id":edge_id,"u":u,"v":v,"highway":hw,
                            "lanes":lanes,"length_m":length_m,
                            "free_flow_speed_kmh":round(ff,2),
                            "free_flow_time_s":round(fft,2),
                            "capacity_pcu_per_hr":round(cap,1),
                            "is_bridge":False,"name":name,
                            "lat_u":ulat,"lon_u":ulon,"lat_v":vlat,"lon_v":vlon})
        edge_id += 1

    # node GeoDataFrame
    nodes_rows = [{"node_id":nid,"y":lat,"x":lon,"name":n,
                   "is_signalised":(nid in {0,2,3,6,9}),
                   "geometry":Point(lon,lat)}
                  for nid,lat,lon,n in NODES]
    nodes_gdf  = gpd.GeoDataFrame(nodes_rows, geometry="geometry", crs="EPSG:4326")
    edges_gdf  = pd.DataFrame(edges_rows)

    # Save graph (strip geometry; GraphML can't serialise Shapely objects)
    G_save = nx.MultiDiGraph()
    for nid, nd in G.nodes(data=True):
        G_save.add_node(nid, **{k: v for k, v in nd.items() if k != "geometry"})
    for u2, v2, k2, ed in G.edges(data=True, keys=True):
        G_save.add_edge(u2, v2, key=k2, **{k: v for k, v in ed.items() if k != "geometry"})
    nx.write_graphml(G_save, str(out_dir / "network.graphml"))
    edges_gdf.to_parquet(out_dir / "edges.parquet", index=False)
    nodes_gdf.to_parquet(out_dir / "nodes.parquet", index=False)

    # Edge speeds by slot
    slots = ["night_offpeak","morning_peak","midday","evening_peak"]
    speed_rows = []
    for _, r in edges_gdf.iterrows():
        hw = r["highway"]
        ff = r["free_flow_speed_kmh"]
        for slot in slots:
            cong = CONGESTION[slot].get(hw, CONGESTION[slot].get("tertiary",1.2))
            spd  = ff / cong
            speed_rows.append({"edge_id":int(r["edge_id"]),"time_slot":slot,
                                "speed_kmh":round(spd,2),"congestion_ratio":round(cong,3),
                                "source":"synthetic_demo"})
    pd.DataFrame(speed_rows).to_parquet(out_dir / "edge_speeds_by_slot.parquet", index=False)

    # Bus routes
    routes_rows = [{k:v for k,v in r.items() if k != "edge_path"} for r in BUS_ROUTES]
    pd.DataFrame(routes_rows).to_parquet(out_dir / "bus_routes.parquet", index=False)

    # Bus route edges
    re_rows = []
    for r in BUS_ROUTES:
        for seq, eid in enumerate(r["edge_path"]):
            re_rows.append({"route_id":r["route_id"],"seq":seq,"edge_id":eid})
    pd.DataFrame(re_rows).to_parquet(out_dir / "bus_route_edges.parquet", index=False)
    pd.DataFrame(re_rows).to_parquet(out_dir / "bus_stops.parquet", index=False)

    # Metro
    pd.DataFrame(METRO_STATIONS).to_parquet(out_dir / "metro_stations.parquet", index=False)

    # BPR params
    bpr = {rc: {"alpha":0.15,"beta":4.0} for rc in
           ["motorway","trunk","primary","secondary","tertiary","residential","unclassified","service"]}
    (out_dir / "bpr_params.json").write_text(json.dumps(bpr, indent=2))

    # metadata
    meta = {"version":"0.1.0-demo","build_date":"2026-10-15","osm_extract_date":"synthetic",
            "study_area":{"north":12.96,"south":12.89,"east":77.66,"west":77.60},
            "node_count":len(NODES),"edge_count":len(edges_rows),
            "total_length_km":round(sum(r["length_m"] for r in edges_rows)/1000,2),
            "config_hash":"demo","note":"Synthetic demo data for Bengaluru Silk Board corridor"}
    (out_dir / "metadata.json").write_text(json.dumps(meta, indent=2))

    print(f"[OK] Demo data generated: {len(NODES)} nodes, {len(edges_rows)} edges -> {out_dir}")
    return G, edges_gdf, nodes_gdf

if __name__ == "__main__":
    root = Path(__file__).parent.parent
    build(root / "data" / "processed")
