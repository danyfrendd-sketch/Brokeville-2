#!/usr/bin/env python3
"""Render a clean, stylized vector map from downloaded Pietarsaari OSM geometry."""
from __future__ import annotations
import json
from pathlib import Path
from html import escape

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "pietarsaari_osm.geojson"
OUTPUT = ROOT / "data" / "pietarsaari_map.svg"
WIDTH, HEIGHT, PAD = 1800, 1400, 35

def rings_for(g):
    typ, c = g.get("type"), g.get("coordinates", [])
    if typ == "Polygon":
        return [c[0]] if c else []
    if typ == "MultiPolygon":
        return [poly[0] for poly in c if poly]
    return []

def lines_for(g):
    typ, c = g.get("type"), g.get("coordinates", [])
    if typ == "LineString":
        return [c]
    if typ == "MultiLineString":
        return c
    return []

def main():
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    features = data.get("features", [])
    points = []
    def collect(obj):
        if isinstance(obj, list) and obj and isinstance(obj[0], (int, float)) and len(obj) >= 2:
            points.append((obj[0], obj[1]))
        elif isinstance(obj, list):
            for v in obj: collect(v)
    for f in features:
        collect((f.get("geometry") or {}).get("coordinates", []))
    if not points:
        raise SystemExit("GeoJSON has no drawable coordinates")
    minx, maxx = min(p[0] for p in points), max(p[0] for p in points)
    miny, maxy = min(p[1] for p in points), max(p[1] for p in points)
    sx, sy = (WIDTH-2*PAD)/max(maxx-minx,1e-9), (HEIGHT-2*PAD)/max(maxy-miny,1e-9)
    scale = min(sx, sy)
    ox, oy = (WIDTH-(maxx-minx)*scale)/2, (HEIGHT-(maxy-miny)*scale)/2
    def xy(p):
        return ox+(p[0]-minx)*scale, HEIGHT-(oy+(p[1]-miny)*scale)
    def path_coords(coords, close=False):
        pts = [xy(p) for p in coords]
        if not pts: return ""
        d = f"M {pts[0][0]:.1f},{pts[0][1]:.1f} " + " ".join(f"L {x:.1f},{y:.1f}" for x,y in pts[1:])
        return d + (" Z" if close else "")
    parts = [
      f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
      '<rect width="100%" height="100%" fill="#f1eee5"/>',
      '<g stroke-linejoin="round" stroke-linecap="round">'
    ]
    # Land-use and building footprints first, beneath transport.
    for f in features:
        g, p = f.get("geometry") or {}, f.get("properties") or {}
        for ring in rings_for(g):
            if len(ring) < 4: continue
            if "building" in p:
                fill, stroke, sw = "#d6bda5", "#a88b74", 0.55
            elif p.get("natural") == "water" or p.get("water") or p.get("landuse") == "reservoir":
                fill, stroke, sw = "#9bcbd7", "#78b5c4", 0.75
            elif p.get("landuse") in ("forest", "grass", "meadow", "recreation_ground", "village_green") or p.get("leisure") in ("park", "garden", "nature_reserve"):
                fill, stroke, sw = "#c6d7b8", "#a9c19a", 0.55
            elif p.get("landuse") in ("industrial", "commercial", "retail"):
                fill, stroke, sw = "#e5d9c5", "#d1c3ad", 0.45
            elif p.get("landuse") in ("residential", "allotments"):
                fill, stroke, sw = "#eae4d7", "#d9d1c3", 0.35
            else:
                continue
            parts.append(f'<path d="{path_coords(ring, True)}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')
    lines = []
    for f in features:
        g = f.get("geometry") or {}
        for line in lines_for(g):
            lines.append((f, line))
    def rank(item):
        p = item[0].get("properties") or {}
        h = p.get("highway")
        return 0 if p.get("natural") == "coastline" else 1 if p.get("waterway") else 2 if p.get("railway") else 3 if h in ("motorway","trunk","primary") else 4 if h in ("secondary","tertiary") else 5
    # Draw outlines for major roads, then road surfaces, so streets remain legible.
    for f, coords in sorted(lines, key=rank):
        p = f.get("properties") or {}
        if len(coords) < 2: continue
        h = p.get("highway")
        if p.get("natural") == "coastline":
            color, sw = "#6baabd", 2.4
        elif p.get("waterway") or p.get("natural") == "water":
            color, sw = "#8bc4d1", 1.8
        elif p.get("railway"):
            color, sw = "#927387", 1.5
        elif h in ("motorway","trunk","primary"):
            color, sw = "#d5b98e", 7.0
        elif h in ("secondary","tertiary"):
            color, sw = "#d8d0c0", 4.8
        elif h:
            color, sw = "#fffdf7", 2.6
        else:
            continue
        dash = ' stroke-dasharray="7 5"' if p.get("railway") else ""
        parts.append(f'<path d="{path_coords(coords)}" fill="none" stroke="{color}" stroke-width="{sw}"{dash}/>')
    parts.extend(['</g>',
      '<g font-family="Arial, sans-serif" fill="#34434a">',
      '<text x="42" y="58" font-size="30" font-weight="700">PIETARSAARI / JAKOBSTAD</text>',
      '<text x="44" y="84" font-size="15">OpenStreetMap vector data • © OpenStreetMap contributors</text>',
      f'<text x="{WIDTH-42}" y="{HEIGHT-28}" font-size="13" text-anchor="end">{len(features):,} mapped features</text>',
      '</g></svg>'])
    OUTPUT.write_text("\n".join(parts), encoding="utf-8")
    print(f"Wrote vector map: {OUTPUT} ({len(features)} features)")
if __name__ == "__main__":
    main()
