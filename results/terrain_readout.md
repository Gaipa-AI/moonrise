# First terrain readout

**Status:** measured, exploratory result from the uploaded rasters. This is a
terrain-only comparison, not a trained ML prediction or a site recommendation.

## Data and method

- Earth elevation: NASA SRTMGL1 V003. Used the named tiles `S21E025`, `S02E036`,
  and `N25E039`; all three were the expected 3601 × 3601 signed 16-bit HGT
  grids. Generic copies in the upload were exact duplicates and were not used.
- Moon elevation: LRO LOLA GDR `LDEM_75S_240M` south-polar map. A 20 km square
  centered on representative Slater Plain candidate point SP01
  (87.478°S, 124.521°E) was summarized. The point comes from a published
  candidate-site table; this window is not the official landing-region polygon.
- Mars elevation: MGS MOLA MEGDR 128 pixels/degree, `megt44n000hb`, with a
  roughly 20 km window centered on the Perseverance landing coordinates in
  Jezero crater.
- Earth DEMs were block-averaged to approximately 0.5 km cells; LOLA was
  averaged to 0.48 km; MOLA is approximately 0.46 km at this latitude.
- Features: p95–p05 relief, mean slope, and mean standard deviation in a 3 × 3
  neighborhood of the harmonized elevation grid.

## Measured terrain features

| Region | p95–p05 relief (m) | Mean slope (°) | 3 × 3 elevation SD (m) |
|---|---:|---:|---:|
| Makgadikgadi Pans | 8.06 | 0.095 | 0.74 |
| Lake Magadi | 266.39 | 1.798 | 13.96 |
| Harrat Khaybar | 548.33 | 2.850 | 20.39 |
| Jezero MOLA reference | 762.05 | 2.816 | 18.66 |
| Slater Plain / SP01 LOLA reference | 1464.75 | 7.453 | 52.62 |

## Provisional terrain scores

The original Moon-and-Mars score table is
[`terrain_comparison_v2.json`](terrain_comparison_v2.json). It uses a transparent
relative linear similarity formula per feature and averages the three features
equally. With the default scale factor of 2.0:

- **Against Jezero:** Harrat Khaybar 93.58, Lake Magadi 78.94, Makgadikgadi 51.40.
- **Against Slater Plain SP01:** Harrat Khaybar 69.07, Lake Magadi 61.47,
  Makgadikgadi 50.54.

Both orders are unchanged at the tested scale factors 1.0, 1.5, 2.0, and 3.0,
but these candidates are a small, preselected sample; neither set is a global
Earth ranking.

## Higher-resolution Slater Plain follow-up

I extracted a 20 km square centered at SP01 from NASA GSFC PGDA's
`LDEM_80S_20MPP_ADJ.TIF` cloud-optimized LOLA DEM. The parent product is 20 m/pixel
and 2.6 GB; the locally retained crop is only about 3.5 MB. NASA also provides a
5 m/pixel LOLA mosaic for the 87–90°S area, but the 20 m cloud-optimized product
was more efficient for this regional comparison. The nominal pixel size is not
the same as effective resolution: LOLA samples are sparse in places and the DEM
is interpolated between tracks.

| Slater Plain SP01 window / scale | p95–p05 relief (m) | Mean slope (°) | Mean 3 × 3 elevation SD (m) |
|---|---:|---:|---:|
| 20 m grid | 1458.03 | 8.874 | 2.59 |
| 100 m aggregated | 1458.07 | 8.399 | 12.24 |
| 500 m aggregated | 1456.18 | 7.478 | 55.05 |

The 500 m summaries are close to the earlier 240 m LOLA result (1464.75 m,
7.453°, 52.62 m), which is a useful scale-consistency check. At the harmonized
500 m support, the provisional Moon scores are Harrat Khaybar 68.80, Lake Magadi
61.28, and Makgadikgadi Pans 50.53. The corresponding expanded results and
per-feature values are in [`terrain_comparison_v3.json`](terrain_comparison_v3.json);
the former scores remain in v2 for provenance. These are regional-window scores:
the 20 km window includes surrounding topography and is not a measurement of
the level plain alone.

## SP01 exploration zone versus adjacent terrain

I used Wueller et al.'s published SP01 point and 2 km exploration-area polygon,
then compared it with a project-defined 2–4 km annulus outside the polygon. The
archive also contains a raster of areas meeting the paper's HLS landing
criteria: slopes from 0–8° and a 100 m buffer from steeper terrain. The paper
reports 77 km² meeting those criteria across the full Slater Plain region; the
SP01 exploration zone contains 1.816 km² of those pixels (13.6% of the local
zone). [Dataset archive](https://zenodo.org/records/17084058), [study and
method](https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2025JE009434).

| SP01 area at 20 m DEM scale | Relief p95–p05 (m) | Mean slope (°) | 3 × 3 elevation SD (m) |
|---|---:|---:|---:|
| Full 2 km exploration polygon | 397.55 | 9.971 | 2.92 |
| Published HLS-suitable pixels inside polygon | 99.62 | 3.358 | 0.98 |
| Adjacent 2–4 km reference annulus | 878.96 | 9.300 | 2.72 |

The suitable landing patches have lower relief and slope than the whole walking
zone. The full zone's mean slope exceeds 8° because it includes the surrounding
craters and rims, while only 13.6% of it is marked suitable in the published
mask. The adjacent annulus is a local reference we defined for this prototype;
it is not an official lunar-region boundary. The mask is a study criterion, not
a landing-safety certification. Detailed values are in
[`slater_sp01_zone_analysis.json`](../data/processed/slater_sp01_zone_analysis.json);
the map is
[`slater_sp01_zone_map.png`](../data/processed/slater_sp01_zone_map.png).

The strongest numerical match for Harrat Khaybar is slope and local roughness;
its regional relief remains lower than Jezero's. Makgadikgadi's low relief is
consistent with its pan setting, but it is a weak match to this rugged Jezero
window on the terrain features measured here. That does not negate its value
for studying Martian playa deposits, mineral processes, or subsurface radar.

## Limits and next checks

- These summaries depend on ROI placement and spatial scale. They do not
  capture small rocks, trafficability, geologic composition, or hazards.
- Earth HGT tiles are elevation surface models and have a distinct observation
  context from planetary laser altimetry.
- MOLA includes interpolated cells; this window is regional-scale and must not
  be used to infer rover-scale roughness.
- The 20 km Slater Plain window is centered on a published representative point,
  not a geologic boundary of the Artemis candidate region.
- The published 2 km polygon is SP01's exploration buffer, not the full Slater
  Plain boundary; the adjacent annulus is project-defined.
- The supplied 240 m LOLA product supports regional relief, but cannot resolve
  many small craters, boulders, or landing hazards. The 20 m follow-up improves
  regional characterization but still does not support boulder-scale claims.
  NASA GSFC's 5 m/pixel 87–90°S mosaic remains the follow-up for finer-scale
  crater morphology, with the same caution about interpolated LOLA cells.
- Next data families should be added separately: thermal observations,
  surface-material/mineral evidence, and water/ice or dust processes. Preserve
  their own coverage and uncertainty, and only then consider model training.
