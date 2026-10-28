#!/usr/bin/env python3
"""Build an approximate real-elevation 3D GLB from OSM building and road footprints."""
from __future__ import annotations
import json, math, time, urllib.parse, urllib.request
from pathlib import Path
import numpy as np
import trimesh
from shapely.geometry import Polygon, LineString, MultiPolygon
from shapely.ops import unary_union, triangulate

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "pietarsaari_osm.geojson"
OUTPUT = ROOT / "data" / "pietarsaari_3d.glb"
GRID = 61  # finer elevation grid: 60 x 60 terrain cells
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
    for start in range(0, len(locations), 80):
        batch = locations[start:start+80]
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


def numeric_tag(value):
    if value is None:
        return None
    try:
        return float(str(value).lower().replace("meters", "").replace("meter", "").replace("metres", "").replace("metre", "").replace("m", "").strip())
    except (TypeError, ValueError):
        return None


def osm_colour(value, fallback):
    if not value:
        return fallback
    name = str(value).strip().lower().replace(" ", "")
    palette = {
        "white": (226, 222, 210, 255), "ivory": (220, 213, 190, 255),
        "cream": (218, 204, 170, 255), "beige": (190, 166, 140, 255),
        "yellow": (205, 181, 103, 255), "orange": (190, 120, 70, 255),
        "red": (151, 75, 63, 255), "brown": (112, 78, 59, 255),
        "grey": (139, 139, 132, 255), "gray": (139, 139, 132, 255),
        "lightgrey": (180, 178, 169, 255), "darkgrey": (90, 90, 86, 255),
        "black": (55, 54, 52, 255), "green": (105, 126, 87, 255),
        "blue": (93, 127, 151, 255),
    }
    if name in palette:
        return palette[name]
    if name.startswith("#"):
        h = name[1:]
        try:
            if len(h) == 3:
                h = "".join(c * 2 for c in h)
            if len(h) == 6:
                return tuple(int(h[i:i+2], 16) for i in (0, 2, 4)) + (255,)
        except ValueError:
            pass
    return fallback


def ground_z(x, y, elevations, zbase):
    # Bilinear interpolation avoids stair-step heights on roads and landcover.
    gx = float(np.clip((x + EXTENT) / (2 * EXTENT) * (GRID - 1), 0, GRID - 1))
    gy = float(np.clip((y + EXTENT) / (2 * EXTENT) * (GRID - 1), 0, GRID - 1))
    x0, y0 = int(math.floor(gx)), int(math.floor(gy))
    x1, y1 = min(x0 + 1, GRID - 1), min(y0 + 1, GRID - 1)
    tx, ty = gx - x0, gy - y0
    a = elevations[y0, x0] * (1 - tx) + elevations[y0, x1] * tx
    b = elevations[y1, x0] * (1 - tx) + elevations[y1, x1] * tx
    return float(a * (1 - ty) + b * ty - zbase)


def draped_polygon_mesh(poly, elevations, zbase, lift=0.03):
    # Triangulate each road/land polygon and put every vertex on the terrain.
    vertices, faces, index = [], [], {}
    for tri in triangulate(poly):
        if not poly.covers(tri.representative_point()):
            continue
        face = []
        for x, y in list(tri.exterior.coords)[:3]:
            key = (round(x, 4), round(y, 4))
            if key not in index:
                index[key] = len(vertices)
                vertices.append([x, y, ground_z(x, y, elevations, zbase) + lift])
            face.append(index[key])
        if len(face) == 3:
            faces.append(face)
    if not faces:
        return None
    return trimesh.Trimesh(vertices=np.asarray(vertices), faces=np.asarray(faces), process=False)


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
    land_meshes = 0
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
        landuse = str(props.get("landuse", "")).lower()
        leisure = str(props.get("leisure", "")).lower()
        natural = str(props.get("natural", "")).lower()
        water_tag = str(props.get("water", "")).lower()
        is_water = natural in ("water", "wetland") or bool(water_tag) or landuse in ("reservoir", "basin") or leisure == "water_park"
        is_green = landuse in ("grass", "meadow", "forest", "village_green", "recreation_ground", "orchard", "allotments") or leisure in ("park", "garden", "golf_course", "nature_reserve", "pitch") or natural in ("wood", "scrub", "heath")
        if "building" in props:
            height = numeric_tag(props.get("height")) or numeric_tag(props.get("building:height"))
            if height is None:
                levels = numeric_tag(props.get("building:levels"))
                if levels is not None:
                    height = max(1, levels) * 3.0 + (numeric_tag(props.get("roof:height")) or 0.0)
                else:
                    kind = str(props.get("building", "")).lower()
                    height = 5.5 if kind in ("house", "detached", "bungalow", "cabin", "shed", "garage") else 9.0
            height = min(max(height, 3.0), 80.0)
            facade = osm_colour(props.get("building:colour") or props.get("building:color"), [190, 166, 140, 255])
            roof_colour = osm_colour(props.get("roof:colour") or props.get("roof:color"), [105, 83, 70, 255])
            for ring in raw_polys:
                if len(ring) < 4: continue
                poly = Polygon([xy(p[0], p[1]) for p in ring])
                if not poly.is_valid: poly = poly.buffer(0)
                for part in polygon_parts(poly):
                    if part.area < 8 or not part.is_valid: continue
                    try:
                        mesh = trimesh.creation.extrude_polygon(part, height, engine="earcut")
                        base_z = ground_z(part.centroid.x, part.centroid.y, elevations, zbase) + 0.10
                        mesh.apply_translation([0, 0, base_z])
                        face_colours = np.tile(np.asarray(facade, dtype=np.uint8), (len(mesh.faces), 1))
                        top_faces = mesh.face_normals[:, 2] > 0.75
                        face_colours[top_faces] = np.asarray(roof_colour, dtype=np.uint8)
                        mesh.visual.face_colors = face_colours
                        scene.add_geometry(mesh, node_name=f"building_{buildings}")
                        buildings += 1
                    except Exception:
                        continue
        elif (is_water or is_green) and raw_polys:
            fill = [77, 139, 166, 255] if is_water else ([75, 112, 67, 255] if landuse == "forest" or natural == "wood" else [108, 143, 83, 255])
            for ring in raw_polys:
                if len(ring) < 4: continue
                poly = Polygon([xy(p[0], p[1]) for p in ring])
                if not poly.is_valid: poly = poly.buffer(0)
                for part in polygon_parts(poly):
                    if part.area < 12 or not part.is_valid: continue
                    try:
                        mesh = draped_polygon_mesh(part, elevations, zbase, lift=0.045)
                        if mesh is None: continue
                        mesh.visual.face_colors = fill
                        scene.add_geometry(mesh, node_name=f"landcover_{land_meshes}")
                        land_meshes += 1
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
                mesh = draped_polygon_mesh(part, elevations, zbase, lift=0.12)
                if mesh is None: continue
                mesh.visual.face_colors = [75, 75, 72, 255]
                scene.add_geometry(mesh, node_name=f"road_{road_meshes}")
                road_meshes += 1
            except Exception:
                continue

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    scene.export(OUTPUT)
    print(f"3D GLB: {OUTPUT} ({OUTPUT.stat().st_size} bytes)")
    print(f"Terrain grid: {GRID}x{GRID}; road and land surfaces draped over terrain; elevation range: {elevations.min():.1f}–{elevations.max():.1f} m")
    print(f"Buildings extruded: {buildings}; land/water polygons: {land_meshes}; road segments meshed: {road_meshes}")
    print("Building footprints and available height/colour tags use OSM data; missing heights are estimated from floor count or building type.")
    print("Data attribution: © OpenStreetMap contributors, ODbL 1.0.")
if __name__ == "__main__":
    main()
