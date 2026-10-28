#!/usr/bin/env python3
"""Render a compact, crisp vector map from downloaded Pietarsaari OSM geometry."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "pietarsaari_osm.geojson"
OUTPUT = ROOT / "data" / "pietarsaari_map.svg"

# Slightly more compact canvas; SVG stays vector-sharp at any zoom.
WIDTH, HEIGHT, PAD = 1600, 1200, 42


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
            for value in obj:
                collect(value)

    for feature in features:
        collect((feature.get("geometry") or {}).get("coordinates", []))
    if not points:
        raise SystemExit("GeoJSON has no drawable coordinates")

    minx, maxx = min(p[0] for p in points), max(p[0] for p in points)
    miny, maxy = min(p[1] for p in points), max(p[1] for p in points)
    sx = (WIDTH - 2 * PAD) / max(maxx - minx, 1e-9)
    sy = (HEIGHT - 2 * PAD) / max(maxy - miny, 1e-9)
    scale = min(sx, sy)
    ox = (WIDTH - (maxx - minx) * scale) / 2
    oy = (HEIGHT - (maxy - miny) * scale) / 2

    def xy(point):
        return ox + (point[0] - minx) * scale, HEIGHT - (oy + (point[1] - miny) * scale)

    def path_coords(coords, close=False):
        pts = [xy(point) for point in coords]
        if not pts:
            return ""
        path = f"M {pts[0][0]:.2f},{pts[0][1]:.2f} " + " ".join(
            f"L {x:.2f},{y:.2f}" for x, y in pts[1:]
        )
        return path + (" Z" if close else "")

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
        '<rect width="100%" height="100%" fill="#f1eee5"/>',
        '<g stroke-linejoin="round" stroke-linecap="round">',
    ]

    # Draw land parcels, parks, water, and building footprints first.
    for feature in features:
        geometry = feature.get("geometry") or {}
        props = feature.get("properties") or {}
        for ring in rings_for(geometry):
            if len(ring) < 4:
                continue
            if "building" in props:
                fill, stroke, stroke_width = "#d6bda5", "#9f8068", 0.65
            elif props.get("natural") == "water" or props.get("water") or props.get("landuse") == "reservoir":
                fill, stroke, stroke_width = "#9bcbd7", "#70adbd", 0.8
            elif props.get("landuse") in ("forest", "grass", "meadow", "recreation_ground", "village_green") or props.get("leisure") in ("park", "garden", "nature_reserve"):
                fill, stroke, stroke_width = "#c6d7b8", "#a2bc91", 0.65
            elif props.get("landuse") in ("industrial", "commercial", "retail"):
                fill, stroke, stroke_width = "#e5d9c5", "#c9b99f", 0.55
            elif props.get("landuse") in ("residential", "allotments"):
                fill, stroke, stroke_width = "#eae4d7", "#d4cbbb", 0.45
            else:
                continue
            parts.append(
                f'<path d="{path_coords(ring, True)}" fill="{fill}" '
                f'stroke="{stroke}" stroke-width="{stroke_width}"/>'
            )

    lines = []
    for feature in features:
        geometry = feature.get("geometry") or {}
        for line in lines_for(geometry):
            lines.append((feature, line))

    def rank(item):
        props = item[0].get("properties") or {}
        highway = props.get("highway")
        if props.get("natural") == "coastline":
            return 0
        if props.get("waterway"):
            return 1
        if props.get("railway"):
            return 2
        if highway in ("motorway", "trunk", "primary"):
            return 3
        if highway in ("secondary", "tertiary"):
            return 4
        return 5

    # Cased major roads improve contrast and keep intersections readable.
    for feature, coords in sorted(lines, key=rank):
        props = feature.get("properties") or {}
        if len(coords) < 2:
            continue
        highway = props.get("highway")
        if props.get("natural") == "coastline":
            color, stroke_width = "#6baabd", 2.5
        elif props.get("waterway") or props.get("natural") == "water":
            color, stroke_width = "#8bc4d1", 1.9
        elif props.get("railway"):
            color, stroke_width = "#927387", 1.7
        elif highway in ("motorway", "trunk", "primary"):
            # pale casing beneath the road surface
            path = path_coords(coords)
            parts.append(f'<path d="{path}" fill="none" stroke="#fffaf0" stroke-width="9.0"/>')
            color, stroke_width = "#d5b98e", 5.8
        elif highway in ("secondary", "tertiary"):
            path = path_coords(coords)
            parts.append(f'<path d="{path}" fill="none" stroke="#fffaf0" stroke-width="6.2"/>')
            color, stroke_width = "#d0c5b1", 3.7
        elif highway:
            color, stroke_width = "#fffdf7", 2.4
        else:
            continue
        dash = ' stroke-dasharray="7 5"' if props.get("railway") else ""
        parts.append(
            f'<path d="{path_coords(coords)}" fill="none" stroke="{color}" '
            f'stroke-width="{stroke_width}"{dash}/>'
        )

    parts.extend([
        '</g>',
        '<g font-family="Arial, sans-serif" fill="#34434a">',
        '<text x="42" y="52" font-size="26" font-weight="700">PIETARSAARI / JAKOBSTAD</text>',
        '<text x="43" y="75" font-size="13">OpenStreetMap vector data • © OpenStreetMap contributors</text>',
        f'<text x="{WIDTH-42}" y="{HEIGHT-24}" font-size="12" text-anchor="end">{len(features):,} mapped features</text>',
        '</g></svg>',
    ])
    OUTPUT.write_text("\n".join(parts), encoding="utf-8")
    print(f"Wrote vector map: {OUTPUT} ({len(features)} features, {WIDTH}x{HEIGHT})")


if __name__ == "__main__":
    main()
