#!/usr/bin/env python3
"""Download real OSM geometry for a compact 5x5 km Pietarsaari/Jakobstad map.

Output: map/data/pietarsaari_osm.geojson
Attribution: © OpenStreetMap contributors, ODbL 1.0.
https://www.openstreetmap.org/copyright
"""
from __future__ import annotations
import json, time, urllib.parse, urllib.request
from pathlib import Path

# Approximate 5 x 5 km area around central Pietarsaari/Jakobstad.
# Latitude: 1 degree ~= 111 km; longitude here ~= 49 km per degree.
CENTER_LAT, CENTER_LON = 63.674, 22.704
HALF_LAT = 2.5 / 111.0
HALF_LON = 2.5 / (111.0 * 0.447)
SOUTH, WEST = CENTER_LAT - HALF_LAT, CENTER_LON - HALF_LON
NORTH, EAST = CENTER_LAT + HALF_LAT, CENTER_LON + HALF_LON

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
MID_LAT, MID_LON = (SOUTH + NORTH) / 2, (WEST + EAST) / 2
TILES = [
    (SOUTH, WEST, MID_LAT, MID_LON),
    (SOUTH, MID_LON, MID_LAT, EAST),
    (MID_LAT, WEST, NORTH, MID_LON),
    (MID_LAT, MID_LON, NORTH, EAST),
]
QUERY_TEMPLATE = """
[out:json][timeout:90];
(
  way["building"]({s},{w},{n},{e});
  way["highway"]({s},{w},{n},{e});
  way["railway"]({s},{w},{n},{e});
  way["waterway"]({s},{w},{n},{e});
  way["natural"="coastline"]({s},{w},{n},{e});
  way["natural"="water"]({s},{w},{n},{e});
  way["landuse"]({s},{w},{n},{e});
  way["leisure"]({s},{w},{n},{e});
);
out geom;
"""

def fetch_tile(tile, tile_no):
    s, w, n, e = tile
    query = QUERY_TEMPLATE.format(s=s, w=w, n=n, e=e)
    body = urllib.parse.urlencode({"data": query}).encode()
    errors = []
    for attempt in range(2):
        for endpoint in OVERPASS_ENDPOINTS:
            try:
                req = urllib.request.Request(endpoint, data=body, headers={
                    "User-Agent": "Brokeville2-map-builder/0.5 (single cached geometry source)"
                }, method="POST")
                with urllib.request.urlopen(req, timeout=75) as response:
                    result = json.load(response)
                print(f"Tile {tile_no}/4: received {len(result.get('elements', []))} OSM elements")
                return result.get("elements", [])
            except Exception as exc:
                errors.append(f"{endpoint}: {exc}")
                time.sleep(1 + attempt)
    raise RuntimeError(f"Tile {tile_no}/4 failed after retries: " + " | ".join(errors[-3:]))

def way_feature(element):
    geom = element.get("geometry")
    if not geom or len(geom) < 2:
        return None
    coords = [[p["lon"], p["lat"]] for p in geom]
    closed = len(coords) >= 4 and coords[0] == coords[-1]
    tags = element.get("tags", {})
    polygon_tags = any(k in tags for k in ("building", "landuse", "leisure", "natural", "water"))
    geometry = {"type": "Polygon", "coordinates": [coords]} if closed and polygon_tags else {"type": "LineString", "coordinates": coords}
    return {
        "type": "Feature",
        "id": f"osm-{element.get('type')}-{element.get('id')}",
        "properties": {"osm_type": element.get("type"), "osm_id": element.get("id"), **tags},
        "geometry": geometry,
    }

def main():
    root = Path(__file__).resolve().parents[1]
    out_dir = root / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    elements_by_id = {}
    for i, tile in enumerate(TILES, 1):
        for element in fetch_tile(tile, i):
            elements_by_id[f"{element.get('type')}-{element.get('id')}"] = element
        time.sleep(1)
    features = [f for e in elements_by_id.values() if (f := way_feature(e))]
    collection = {
        "type": "FeatureCollection",
        "name": "Pietarsaari_Jakobstad_OSM_source",
        "metadata": {
            "source": "OpenStreetMap via Overpass API",
            "bbox_south_west_north_east": [SOUTH, WEST, NORTH, EAST],
            "approximate_extent_km": [5.0, 5.0],
            "feature_count": len(features),
            "downloaded_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "license": "ODbL 1.0",
            "attribution": "© OpenStreetMap contributors",
            "note": "Mapped OSM ways only are rendered. Relation multipolygons and unmapped features require additional processing."
        },
        "features": features,
    }
    path = out_dir / "pietarsaari_osm.geojson"
    path.write_text(json.dumps(collection, ensure_ascii=False), encoding="utf-8")
    print(f"Map extent: approximately 5 x 5 km, bbox {SOUTH:.5f},{WEST:.5f},{NORTH:.5f},{EAST:.5f}")
    print(f"Wrote {len(features)} unique features to {path} ({path.stat().st_size} bytes)")

if __name__ == "__main__":
    main()
