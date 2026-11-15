# Field Analog Atlas

An interactive static research prototype for exploring Earth terrain candidates against Slater Plain (Moon) and Jezero crater (Mars).

## Run locally

From this directory, start a static web server in PowerShell:

```powershell
& 'py -m http.server 8000
```

Then open <http://localhost:8000>. If Python is on your PATH, `py -m http.server 8000` also works. The browser needs access to the internet to load Three.js, Google Fonts, and remote NASA/ESA base imagery. The analysis outputs and Slater map are included in the app assets.

## Evidence shown

- Scores and per-feature values come directly from `../results/terrain_comparison_v3.json`.
- All scores are exploratory, terrain-only values for three preselected Earth candidates; they are neither ML predictions nor probabilities.
- Moon target image: `assets/slater_sp01_zone_map.png`, copied from the project Slater SP01 analysis. It is an orbital analysis map because no ground-level photograph exists for the location.
- Jezero landscape: NASA/JPL/ASU/MSSS Mastcam-Z landscape imagery. The displayed crop is intended to show terrain only.
- Earth image sources are linked in the site detail panel: NASA Earth Observatory for Harrat Khaybar, ESA/Copernicus Sentinel-2 for Lake Magadi, and NASA Visible Earth for Makgadikgadi Pans.
- The global Moon texture is NASA LROC/LOLA CGI Moon Kit. Earth is NASA Blue Marble. Mars uses a NASA Mars global view texture; if unavailable, the globe retains its shaded Mars-color fallback.

## Interpretation and limitations

The three measured features are P95–P05 local relief, mean slope, and 3×3-cell elevation standard deviation, harmonized to roughly 500 m cells. The score uses an equal-weight relative-distance formula (scale factor 2). Mineralogy, temperature, dust, illumination, water/ice, and operational risk are not scored. Candidate text describes research hypotheses and mismatch context, not validated site suitability.
