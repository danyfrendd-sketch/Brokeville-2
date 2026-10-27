# Brokeville 2 — Map Skeleton

This folder is the source-of-truth for the first map pass. The supplied reference image is a **schematic**, not a surveyed CAD/GIS plan, so this project separates measured image geometry from assumptions.

## Coordinate system

- Reference canvas: **1000 × 536 image pixels**.
- Local origin: top-left of the reference image; X increases right, Y increases down.
- The visible scale bar is labelled 0–10 km. Its endpoints need a precise pixel measurement from the original file before treating world distances as final. The current value in `map-layout.json` is explicitly provisional.
- Trace roads, shoreline, railways, parcels, and building footprints against the reference. Do not add random buildings or silently straighten irregular streets.
- “1:1” for this phase means faithful geometry relative to the supplied reference. It does **not** mean the illustration contains enough information to recover the real-world dimensions of every building.

## Map layers (build in this order)

1. Outer map bounds and out-of-bounds note.
2. River Serpentine, coastline, harbor basins, and piers.
3. H1–H4 highways, interchanges, bridges, and main streets.
4. Railway and rail-logistics terminal.
5. District boundaries.
6. Individual building footprints and landmarks.
7. Labels and legend.

## Reference districts

- Northwest Region / Remote Suburban Enclaves
- Suburban Retail Plaza and School
- Residential Parks
- University Campus
- Financial Quarter
- Bottom-left District / Harbor & Marina
- Central District
- Central Transit Hub
- Industrial Sector
- Heavy Manufacturing (Units A–D)
- Automotive Factory
- Large Chemical Plant (Hazmat)
- Regional Warehouse & Distribution Hub
- Rail Logistics Terminal
- Southeast Region / Expanded Industrial & Logistics Complex

## Accuracy rules

- Store source-image pixel coordinates first; convert to game/world coordinates only through the calibration value.
- Keep source observations distinct from estimates.
- Do not claim building-level 1:1 accuracy until each footprint has been traced and checked against the original image.
- The original reference image is externally hosted at: https://files.catbox.moe/7pq1fv.jpeg
