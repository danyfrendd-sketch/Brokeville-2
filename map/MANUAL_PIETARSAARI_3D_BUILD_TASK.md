# Manual build task: Pietarsaari / Jakobstad walkable 3D map

## Objective
Replace the placeholder/failed auto-generated map with a walkable, metrically consistent 3D reconstruction of central Pietarsaari (Jakobstad), Finland. This is a geometry task, not a screenshot, minimap, or painted illustration.

## Reference sources
1. City map portal: https://pietarsaari.asiointi.fi/IMS — inspect guide map, base map, current detailed plan, and available aerial imagery layers.
2. Google Maps: https://www.google.com/maps?q=Pietarsaari — use for visual cross-checks and street-level inspection where imagery is available.
3. City base-map dataset metadata: https://avoindata.suomi.fi/data/dataset/pietarsaaren-kaupungin-kantakartta — follow published service/metadata and CC BY 4.0 attribution terms.
4. OpenStreetMap can be a supplementary reference, not the sole truth source.

Do not copy Google satellite tiles or Street View imagery into the game. Use imagery to inspect and trace geometry; ship original mesh/materials and keep required dataset attribution.

## Scope and coordinate system
- Target area: approximately 5 km x 5 km centred on 63.674, 22.704.
- Use a local metric coordinate system in metres, with one documented origin and north/up direction.
- Keep a single scale across terrain, roads, buildings and props.
- Preserve actual bends, curves, junction shapes, roundabouts, bridges, coastline and waterfront edges. Do not replace the road network with straightened or guessed lines.

## Required layers (in this order)
1. **Terrain:** continuous ground mesh covering the playable area; land, shoreline, water surface and major terrain transitions. No flat plane as final ground.
2. **Road surfaces:** solid meshes with real widths and junction outlines. Main roads visibly wider than residential streets; include curb/sidewall thickness and bridges where appropriate. Road tops must follow terrain without floating or z-fighting.
3. **Paths and sidewalks:** pedestrian paths, cycleways, sidewalks where source evidence supports them.
4. **Buildings:** trace individual footprints from base-map/aerial references. Extrude using known heights where available; mark estimated heights as estimates. Preserve industrial halls and large complexes as real footprints, not generic cubes.
5. **Water and shore:** harbour basins, coast, channels, piers and quays as separate geometry.
6. **Land cover:** parks, forest patches, grass, paved yards and industrial lots based on mapped evidence.
7. **Landmarks:** only after base geometry is checked.

## Accuracy and verification
- Work in small named sectors (centre, harbour, residential west, industrial east); finish each sector before expanding.
- Save source geometry as editable GeoJSON or equivalent vector files; do not only commit the final GLB.
- Maintain source, confidence, and optional height_source fields for features. Distinguish observed geometry from inferred values.
- Compare the top-down 3D render with the official base map at the same extent. Check every major junction, road connection, coastline bend and large building footprint.
- Add a validation report: counts of roads/buildings/water polygons, bounds, scale/origin, invalid geometries, and top-down mesh screenshots.
- Build a playable GLB and test spawn, collision/ground height, roads, water, and buildings before publishing.

## Deliverables
- Editable source geometry under map/data/manual/.
- A build script that turns source geometry into the game mesh; ordinary geometry edits must not require repeated remote downloads.
- map/preview/pietarsaari_3d.glb and a top-down preview image/SVG.
- A short QA report listing incomplete sectors and estimated heights.
- A visible source-attribution note in the repository.

## Acceptance criteria
- Player can walk on solid road surfaces and continuous ground.
- Roads connect correctly at junctions and follow the real street layout.
- Buildings occupy mapped footprints and do not appear as randomly placed cubes.
- Water and coastline align with the reference.
- The project rebuilds from committed local geometry without fetching OSM/Overpass data again.
- Do not describe the map as 1:1 complete until the QA checklist has passed.
