#!/usr/bin/env python3
"""Build a separate v2 GLB without overwriting the currently served map."""
from pathlib import Path
import build_pietarsaari_3d as builder

builder.OUTPUT = builder.ROOT / "preview" / "pietarsaari_3d_v2.glb"

if __name__ == "__main__":
    if not builder.SOURCE.is_file():
        raise SystemExit(
            f"Missing OSM source: {builder.SOURCE}. "
            "Restore map/data/pietarsaari_osm.geojson before building."
        )
    builder.main()
