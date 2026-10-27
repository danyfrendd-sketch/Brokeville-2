#!/usr/bin/env python3
"""
Download real OpenStreetMap geometry for Pietarsaari/Jakobstad.

Output: map/data/pietarsaari_osm.geojson
Includes mapped buildings, roads, railways, waterways, landuse and coastline.
This is source geometry, not a finished 3D city. Building heights are only present
where mapped. Coordinates in GeoJSON remain WGS84 longitude/latitude.

Usage:
    python tools/download_pietarsaari_osm.py

Attribution: © OpenStreetMap contributors, ODbL 1.0.
https://www.openstreetmap.org/copyright
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

# Broad working area around Pietarsaari; crop to the municipal boundary in a later
# processing step if a boundary polygon is available.
SOUTH, WEST, NORTH, EAST = 63.60, 22.45, 63.82, 22.86
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
QUERY = f"""
[out:json][timeout:180];
(
  way["building"]({SOUTH},{WEST},{NORTH},{EAST});
  relation["building"]({SOUTH},{WEST},{NORTH},{EAST});
  way["highway"]({SOUTH},{WEST},{NORTH},{EAST});
  way["railway"]({SOUTH},{WEST},{NORTH},{EAST});
  way["waterway"]({SOUTH},{WEST},{NORTH},{EAST});
  way["natural"="coastline"]({SOUTH},{WEST},{NORTH},{EAST});
  way["natural"="water"]({SOUTH},{WEST},{NORTH},{EAST});
  way["landuse"]({SOUTH},{WEST},{NORTH},{EAST});
  way["leisure"]({SOUTH},{WEST},{NORTH},{EAST});
);
out geom;
"""

def fetch() -> dict:
    body = urllib.parse.urlencode({"data": QUERY}).encode()
    last_error = None
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            req = urllib.request.Request(
                endpoint, data=body,
                headers={"User-Agent": "Brokeville2-map-builder/0.1 (OSM data downloader)"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=210) as response:
                return json.load(response)
        except Exception as exc:
            last_error = exc
            time.sleep(2)
    raise RuntimeError(f"All Overpass endpoints failed: {last_error}")

def way_feature(element: dict) -> dict | None:
    geom = element.get("geometry")
    if not geom or len(geom) < 2:
        return None
    coords = [[p["lon"], p["lat"]] for p in geom]
    closed = len(coords) >= 4 and coords[0] == coords[-1]
    tags = element.get("tags", {})
    polygon_tags = any(k in tags for k in (
        "building", "landuse", "leisure", "natural", "water"
    ))
    if closed and polygon_tags:
        geometry = {"type": "Polygon", "coordinates": [coords]}
    else:
        geometry = {"type": "LineString", "coordinates": coords}
    return {
        "type": "Feature",
        "id": f"osm-{element.get('type')}-{element.get('id')}",
        "properties": {"osm_type": element.get("type"), "osm_id": element.get("id"), **tags},
        "geometry": geometry,
    }

def main() -> None:
    root = Path(__file__).resolve().parents[1]
    out_dir = root / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    data = fetch()
    features = [f for e in data.get("elements", []) if (f := way_feature(e))]
    collection = {
        "type": "FeatureCollection",
        "name": "Pietarsaari_Jakobstad_OSM_source",
        "metadata": {
            "source": "OpenStreetMap via Overpass API",
            "bbox_south_west_north_east": [SOUTH, WEST, NORTH, EAST],
            "feature_count": len(features),
            "downloaded_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "license": "ODbL 1.0",
            "attribution": "© OpenStreetMap contributors",
            "note": "Mapped source features only; not a complete cadastral survey. Relations and multipolygons may need additional processing."
        },
        "features": features,
    }
    path = out_dir / "pietarsaari_osm.geojson"
    path.write_text(json.dumps(collection, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(features)} features to {path}")

if __name__ == "__main__":
    main()
