#!/usr/bin/env python3
"""Build an approximate real-elevation 3D GLB from OSM building and road footprints."""
from __future__ import annotations
import json, math, time, urllib.parse, urllib.request
from pathlib import Path
import numpy as np
import trimesh
from shapely.geometry import Polygon, LineString, MultiPolygon
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "pietarsaari_osm.geojson"
OUTPUT = ROOT / "data" / "pietarsaari_3d.glb"
GRID = 41  # elevation sample grid: 40 x 40 terrain cells
LAT0, LON0 = 63.674, 22.704
METERS_PER_DEG_LAT = 111320.0
METERS_PER_DEG_LON = 111320.0 * math.cos(math.radians(LAT0))
EXTENT = 2500.0  # half-width in meters: 5 x 5 km total


def xy(lon, lat):
    return ((lon-LON0)*METERS_PER_DEG_LON, (lat-LAT0)*METERS_PER_DEG_LAT)


def get_elevations(locations):
    # Open-Meteo's public elevation endpoint accepts comma-separated coordinates.
    vals = []
    # Keep requests short enough for common URL limits; the API accepts coordinate lists.
    for start in range(0, len(locations), 20):
        batch = locations[start:start+20]
        params = {
            "latitude": ",".join(f"{lat:.6f}" for lat, lon in batch),
            "longitude": ",".join(f"{lon:.6f}" for lat, lon in batch),
        }
        url = "https://api.open-meteo.com/v1/elevation?" + urllib.parse.urlencode(params)
        last = None
        for attempt in range(4):
            try:
                req = urllib.request.Request(url, headers={"User-Agent":"Brokeville2-3D-map/1.0"})
                with urllib.request.urlopen(req, timeout=45) as resp:
                    data = json.load(resp)
                elevations = data.get("elevation")
                if not isinstance(elevations, list):
                    elevations = [elevations]
                if len(elevations) != len(batch) or any(v is None for v in elevations):
                    raise ValueError(f"Elevation API returned {len(elevations)} values for {len(batch)} points")
                vals.extend(float(v) for v in elevations)
                last = None
                break
            except Exception as exc:
                last = exc
                time.sleep(2 + attempt * 2)
        if last:
            raise RuntimeError(f"Elevation lookup failed: {last}")
        time.sleep(0.2)
    return vals


def polygon_parts(geom):
    if isinstance(geom, Polygon):
        return [geom]
    if isinstance(geom, MultiPolygon):
        return list(geom.geoms)
    return []


def main():
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    features = data.get("features", [])
    # Sample terrain across the exact 5 x 5 km build area.
    xs = np.linspace(-EXTENT, EXTENT, GRID)
    ys = np.linspace(-EXTENT, EXTENT, GRID)
    sample_points = []
    for y in ys:
        for x in xs:
            lat = LAT0 + y / METERS_PER_DEG_LAT
            lon = LON0 + x / METERS_PER_DEG_LON
            sample_points.append((lat, lon))
    elevations = np.array(get_elevations(sample_points), dtype=float).reshape((GRID, GRID))
    # Keep vertical exaggeration at 1x; offset sea-level reference for a stable scene.
    zbase = float(np.min(elevations))
    terrain_vertices = []
    for j, y in enumerate(ys):
        for i, x in enumerate(xs):
            terrain_vertices.append([x, y, float(elevations[j, i] - zbase)])
    faces = []
    for j in range(GRID-1):
        for i in range(GRID-1):
            a = j*GRID+i; b=a+1; c=a+GRID; d=c+1
            faces.extend([[a,b,d],[a,d,c]])
    terrain = trimesh.Trimesh(vertices=np.asarray(terrain_vertices), faces=np.asarray(faces), process=False)
    terrain.visual.face_colors = [116, 139, 99, 255]
    scene = trimesh.Scene()
    scene.add_geometry(terrain, node_name="terrain_real_elevation")

    # Buildings use OSM footprints and tagged heights where available; otherwise conservative defaults.
    buildings = 0
    roads = []
    for feat in features:
        props = feat.get("properties") or {}
        geom = feat.get("geometry") or {}
        coords = geom.get("coordinates") or []
        if geom.get("type") == "Polygon":
            raw_polys = [coords[0]] if coords else []
        elif geom.get("type") == "MultiPolygon":
            raw_polys = [p[0] for p in coords if p]
        else:
            raw_polys = []
        if "building" in props:
            try:
                height = float(str(props.get("height", "")).replace("m", "").strip())
            except (ValueError, TypeError):
                height = 8.0 if props.get("building") in ("house", "detached", "residential") else 10.0
            height = min(max(height, 3.0), 80.0)
            for ring in raw_polys:
                if len(ring) < 4: continue
                poly = Polygon([xy(p[0], p[1]) for p in ring])
                if not poly.is_valid: poly = poly.buffer(0)
                for part in polygon_parts(poly):
                    if part.area < 8 or not part.is_valid: continue
                    try:
                        mesh = trimesh.creation.extrude_polygon(part, height, engine="earcut")
                        cx, cy = part.centroid.x, part.centroid.y
                        ix = int(np.clip(round((cx+EXTENT)/(2*EXTENT)*(GRID-1)),0,GRID-1))
                        iy = int(np.clip(round((cy+EXTENT)/(2*EXTENT)*(GRID-1)),0,GRID-1))
                        mesh.apply_translation([0, 0, float(elevations[iy,ix]-zbase)+0.15])
                        mesh.visual.face_colors = [190, 166, 140, 255]
                        scene.add_geometry(mesh, node_name=f"building_{buildings}")
                        buildings += 1
                    except Exception:
                        continue
        elif props.get("highway"):
            for line in (geom.get("coordinates") or [],):
                if geom.get("type") == "LineString" and len(line) >= 2:
                    roads.append((props.get("highway"), LineString([xy(p[0],p[1]) for p in line])))

    # Roads are thin raised strips following the sampled ground surface.
    road_meshes = 0
    for kind, line in roads:
        width = 5.0 if kind in ("primary","trunk","secondary") else 3.0 if kind in ("tertiary","residential","unclassified") else 1.8
        road_poly = line.buffer(width/2, cap_style="flat", join_style="round")
        for part in polygon_parts(road_poly):
            if part.area < 2: continue
            try:
                mesh = trimesh.creation.extrude_polygon(part, 0.08, engine="earcut")
                cx, cy = part.centroid.x, part.centroid.y
                ix = int(np.clip(round((cx+EXTENT)/(2*EXTENT)*(GRID-1)),0,GRID-1))
                iy = int(np.clip(round((cy+EXTENT)/(2*EXTENT)*(GRID-1)),0,GRID-1))
                mesh.apply_translation([0,0,float(elevations[iy,ix]-zbase)+0.25])
                mesh.visual.face_colors = [75, 75, 72, 255]
                scene.add_geometry(mesh, node_name=f"road_{road_meshes}")
                road_meshes += 1
            except Exception:
                continue

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    scene.export(OUTPUT)
    print(f"3D GLB: {OUTPUT} ({OUTPUT.stat().st_size} bytes)")
    print(f"Terrain grid: {GRID}x{GRID}; elevation range: {elevations.min():.1f}–{elevations.max():.1f} m")
    print(f"Buildings extruded: {buildings}; road segments meshed: {road_meshes}")
    print("Building and road positions are based on OSM coordinates; untagged building heights use defaults.")
if __name__ == "__main__":
    main()
