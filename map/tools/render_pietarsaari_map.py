#!/usr/bin/env python3
"""Render a clean, stylized 2D vector map from the downloaded OSM GeoJSON.

This is a map render (not a photo). It preserves source feature coordinates and
styles roads, buildings, water, green areas, railways and other mapped features.
"""
from __future__ import annotations
import json
from pathlib import Path
from html import escape

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "pietarsaari_osm.geojson"
OUTPUT = ROOT / "data" / "pietarsaari_map.svg"
WIDTH, HEIGHT, PAD = 1800, 1400, 35

def main():
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    features = data.get("features", [])
    points = []
    for f in features:
        g = f.get("geometry") or {}
        typ = g.get("type")
        coords = g.get("coordinates", [])
        def collect(obj):
            if isinstance(obj, list) and obj and isinstance(obj[0], (int, float)) and len(obj) >= 2:
                points.append((obj[0], obj[1]))
            elif isinstance(obj, list):
                for v in obj: collect(v)
        collect(coords)
    if not points:
        raise SystemExit("GeoJSON has no drawable coordinates")
    minx = min(p[0] for p in points); maxx = max(p[0] for p in points)
    miny = min(p[1] for p in points); maxy = max(p[1] for p in points)
    sx = (WIDTH - 2*PAD) / max(maxx-minx, 1e-9)
    sy = (HEIGHT - 2*PAD) / max(maxy-miny, 1e-9)
    scale = min(sx, sy)
    ox = (WIDTH - (maxx-minx)*scale)/2
    oy = (HEIGHT - (maxy-miny)*scale)/2
    def xy(p):
        return ox + (p[0]-minx)*scale, HEIGHT - (oy + (p[1]-miny)*scale)
    def path_coords(coords, close=False):
        pts = [xy(p) for p in coords]
        if not pts: return ""
        s = f"M {pts[0][0]:.1f},{pts[0][1]:.1f} " + " ".join(f"L {x:.1f},{y:.1f}" for x,y in pts[1:])
        return s + (" Z" if close else "")
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
             '<rect width="100%" height="100%" fill="#e9e5d7"/>',
             '<g stroke-linejoin="round" stroke-linecap="round">']
    # Draw polygons first so roads and building outlines remain visible.
    for f in features:
        g = f.get("geometry") or {}; props = f.get("properties") or {}; typ = g.get("type"); c = g.get("coordinates", [])
        tags = props
        if typ == "Polygon":
            ring = c[0] if c else []
            if len(ring) < 4: continue
            if "building" in tags: fill, stroke, sw = "#d2b8a2", "#9b806d", 0.65
            elif tags.get("natural") == "water" or "water" in tags or "waterway" in tags: fill, stroke, sw = "#9bcbd5", "#72aab9", 0.8
            elif tags.get("landuse") in ("forest", "grass", "meadow", "recreation_ground") or tags.get("leisure") in ("park", "garden"): fill, stroke, sw = "#b9cda8", "#9db58b", 0.6
            else: continue
            parts.append(f'<path d="{path_coords(ring, True)}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')
    # Main transport and water lines.
    roads = []
    for f in features:
        g = f.get("geometry") or {}; props = f.get("properties") or {}; typ = g.get("type"); c = g.get("coordinates", [])
        if typ == "LineString":
            roads.append((f, c))
        elif typ == "MultiLineString":
            roads.extend((f, line) for line in c)
    def rank(item):
        p = item[0].get("properties") or {}
        h = p.get("highway")
        return 0 if p.get("natural") == "coastline" or p.get("waterway") else 1 if p.get("railway") else 2 if h in ("motorway","trunk","primary") else 3 if h in ("secondary","tertiary") else 4
    for f, coords in sorted(roads, key=rank):
        p = f.get("properties") or {}
        if len(coords) < 2: continue
        if p.get("natural") == "coastline" or p.get("waterway") or p.get("natural") == "water":
            color, sw = "#78b7c8", 2.2
        elif p.get("railway"):
            color, sw = "#8c6678", 1.6
        elif p.get("highway") in ("motorway","trunk","primary"):
            color, sw = "#f7f0dc", 5.0
        elif p.get("highway") in ("secondary","tertiary"):
            color, sw = "#fffaf0", 3.2
        elif p.get("highway"):
            color, sw = "#fffdf7", 1.7
        else:
            continue
        dash = ' stroke-dasharray="6 5"' if p.get("railway") else ""
        parts.append(f'<path d="{path_coords(coords)}" fill="none" stroke="{color}" stroke-width="{sw}"{dash}/>')
    parts.extend(['</g>',
      '<g font-family="Arial, sans-serif" fill="#34434a">',
      '<text x="42" y="58" font-size="30" font-weight="700">PIETARSAARI / JAKOBSTAD</text>',
      '<text x="44" y="84" font-size="15">OSM vector map • source geometry • © OpenStreetMap contributors</text>',
      f'<text x="{WIDTH-42}" y="{HEIGHT-28}" font-size="13" text-anchor="end">{len(features):,} mapped features</text>',
      '</g></svg>'])
    OUTPUT.write_text("\n".join(parts), encoding="utf-8")
    print(f"Wrote vector map: {OUTPUT} ({len(features)} features)")
if __name__ == "__main__":
    main()
