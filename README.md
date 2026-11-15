# Planetary analog research prototype

This module is the evidence and scoring layer for finding Earth locations that
may support lunar or Mars exploration training. It is deliberately separate
from the Lunar Foundation Model fine-tuning code: the latter can help analyze
lunar observations, but it is not a cross-planet similarity model.

## Research rules

- Compare explicit target environments, not whole worlds or a single vague
  "Moon-like" label. First targets are lunar south-polar exploration terrain
  and Mars mid-latitude terrain relevant to surface operations.
- A score means similarity only for its named, measured features. Gravity,
  vacuum/atmospheric pressure, radiation, and reduced gravity cannot be
  represented by Earth surface data; report them as non-analog limitations.
- Use measured and quality-screened raster summaries at a common spatial scale.
  Keep the source product, version, temporal window, resolution, units, quality
  flags, and processing recipe with every feature value.
- Report per-feature matches, coverage, and uncertainty alongside the aggregate.
  Missing values are omitted and weights renormalized; they are never silently
  imputed as a match.
- The initial score is a transparent weighted distance, not a trained ML model.
  Do not call it a probability or a validated prediction. Learn weights or fit
  an ML ranking only after assembling defensible analog/non-analog labels and
  evaluating held-out regions.

## Initial data-backed scope

The first reproducible experiment should compare regional terrain statistics
from Earth DEMs against lunar LOLA and Mars MOLA/HRSC elevation products. For
each region, summarize slope, local relief, and roughness at matched analysis
scales. These measurements support terrain and mobility preparation; they do
not establish geological or environmental equivalence.

Add thermal conditions as a second feature family after choosing a comparable
definition. MODIS observes Earth surface temperature under an Earth atmosphere;
Diviner observes lunar surface temperatures under lunar illumination and
vacuum. Compare distributions/extremes with explicit seasonal and illumination
context, not a simplistic annual-mean temperature distance. Mars targets should
use mission/season-aware surface products. Surface material/mineralogy should
be a separate family because available instruments and spectral bands differ.

The initial Earth shortlist is recorded in [`candidate_sites.json`](candidate_sites.json):
Makgadikgadi Pans (positive-control Mars playa/evaporite case), Lake Magadi
(evaporite-mineral and spectral-mapping case), and Harrat Khaybar (exploratory
basaltic terrain/mobility case). These are complementary hypotheses, not
rankings. Published work already studies Makgadikgadi and Magadi in planetary
contexts; the project can still contribute by applying a consistent, spatially
matched comparison and testing whether a global discovery workflow recovers
them. Harrat Khaybar remains an exploratory candidate pending explicit
planetary-analog and field-suitability review.

## Data acquisition and provenance

Install the third-party Python libraries used by the analysis scripts with
`python -m pip install -r requirement.txt` from this folder. Python standard
library modules are not included in that file.

See [`sources.json`](sources.json) for the initial source register. Large
planetary rasters should not be checked into git. Store downloaded inputs in a
configured data directory, keep checksums and product labels in a manifest, and
derive small regional summaries/tiles for the website. Before release, confirm
each product's current license, citation, coordinate reference, no-data value,
and quality masks from its product documentation.

The Slater Plain high-resolution follow-up is reproducible with
[`extract_slater_20m.py`](extract_slater_20m.py). It range-reads a 20 km crop
around SP01 from NASA PGDA's cloud-optimized `LDEM_80S_20MPP_ADJ.TIF` and stores
the small crop and multiscale feature summary under `data/processed/`. Its
harmonized 500 m comparison is in
[`terrain_comparison_v3.json`](results/terrain_comparison_v3.json). Rasterio is
required by this optional extraction script; NumPy alone is enough to use the
precomputed JSON results. The 20 m pixel spacing does not mean uniform 20 m
effective resolution because the LOLA DEM interpolates between tracks.

The local SP01 comparison is reproducible with
[`analyze_slater_sp01_zone.py`](analyze_slater_sp01_zone.py). It uses the
published 2 km EVA exploration polygon and landing-suitability raster in
`data/raw/Landing_Sites_Wueller_2026.zip`, then compares that zone with the
adjacent 2–4 km annulus. Results and the overview map are under
`data/processed/`. The 2 km polygon is an operational radius around SP01, not
the boundary of the entire Slater Plain candidate region. This workflow needs
Rasterio, PyShp, NumPy, and Pillow.

## Scoring interface

`scoring.py` accepts feature values for an Earth region and a target profile.
Each feature defines a common unit, physically meaningful comparison scale,
weight, and optional uncertainty. The per-feature similarity uses a clipped
linear distance on that scale. The aggregate is the weighted mean across
available features. The result includes coverage and individual contributions
so users can see why a location ranks well or poorly.

Feature scales and weights are research assumptions, not fitted constants.
They must be versioned with each result set. Do not combine unlike themes into
one headline score until the theme weights are justified and sensitivity
analysis shows the ranking is reasonably stable.

## Similarity score table
| Earth site | Slater Plain score | Jezero score |
|---|---:|---:|
| Harrat Khaybar | 69.07 | 93.58 |
| Lake Magadi | 61.47 | 78.94 |
| Makgadikgadi Pans | 50.54 | 51.40 |

## View Interactive Web visual
Launch
`cd webapp && py -m http.server 8000` <br>
Deployed on hugging face
[Sites](https://huggingface.co/spaces/Onyoin/field-analog-atlas)
<br>
<img src="https://files.fm/f/zabkatwsjdbdyvvg" alt="thumbnail" height="30px" width="50px"/>
<br>
[![Project Logo](thumbnail.png)](https://files.fm/f/zabkatwsjdbdyvvg)
<!-- ![Thumbnail]('https://files.fm/f/zabkatwsjdbdyvvg')<br> -->
<!-- ![Thumbnail]('C:\Users\user\Downloads\thumbnail.png') -->


## Search Earth Data from NASA used to process the image & terrain data
Find those files at this link: [data-files](https://files.fm/u/mrqw7844v25p7g66)



## Next implementation steps

1. Introduce more dimensions of analogy such as Temperature, illumination, and environmental    extremes Water, ice, permafrost, and other potential resources Dust, wind, erosion, and other atmospheric or surface processes.
2. Give structure this python scripts used in this project to form an official model that can undergo several self-supervised training schemes and output as a direct data api
2. Locate or construct a clearly labeled Slater Plain candidate-region
   footprint; the current published geometry defines SP01's EVA radius, not the
   region boundary.
3. Add higher-resolution Earth DEM chips before making crater-scale
   cross-planet comparisons; the current SRTM tiles only support the roughly
   0.5 km comparison.
4. Add thermal and material layers as independent score families.
5. Expand beyond the three preselected Earth candidates and test rankings on
   held-out regions.
6. Build the map from the resulting versioned GeoJSON/COG-derived summaries.


Exploratory rankings are saved in `results/`; they use only three preselected
Earth samples and a few topography features, so they are a prototype readout rather
than a global ranking or validated suitability assessment.
