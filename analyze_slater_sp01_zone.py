"""Compare the published SP01 2 km exploration zone with adjacent terrain."""

from __future__ import annotations

import io
import json
import math
import shutil
import tempfile
import zipfile
from pathlib import Path

import numpy as np
import rasterio
import shapefile
from rasterio.features import geometry_mask
from rasterio.warp import Resampling, reproject, transform_geom
from rasterio.windows import from_bounds


HERE = Path(__file__).resolve().parent
ARCHIVE = HERE / "data" / "raw" / "Landing_Sites_Wueller_2026.zip"
DEM_FILE = HERE / "data" / "processed" / "slater_sp01_lola_20m_20km.tif"
OUT = HERE / "data" / "processed" / "slater_sp01_zone_analysis.json"
MAP = HERE / "data" / "processed" / "slater_sp01_zone_map.png"


def reader_from_zip(zf: zipfile.ZipFile, stem: str) -> shapefile.Reader:
    return shapefile.Reader(
        shp=io.BytesIO(zf.read(f"{stem}.shp")),
        shx=io.BytesIO(zf.read(f"{stem}.shx")),
        dbf=io.BytesIO(zf.read(f"{stem}.dbf")),
    )


def polygon_area_km2(geometry: dict) -> float:
    area = 0.0
    for ring in geometry["coordinates"]:
        points = np.asarray(ring, dtype=np.float64)
        area += 0.5 * float(np.sum(points[:-1, 0] * points[1:, 1] - points[1:, 0] * points[:-1, 1]))
    return abs(area) / 1_000_000.0


def summary(dem: np.ndarray, mask: np.ndarray, pixel_m: float) -> dict:
    valid = mask & np.isfinite(dem)
    if valid.sum() < 100:
        raise ValueError(f"Too few valid pixels in zone: {int(valid.sum())}")
    filled = dem.copy()
    filled[~np.isfinite(filled)] = float(np.nanmedian(filled))
    gy, gx = np.gradient(filled, pixel_m, pixel_m)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    slope_values = slope[valid]
    local_std = np.lib.stride_tricks.sliding_window_view(filled, (3, 3)).std(axis=(-2, -1))
    local_mask = valid[1:-1, 1:-1]
    rough_values = local_std[local_mask]
    elev = dem[valid]
    return {
        "valid_pixels": int(valid.sum()),
        "valid_area_km2": round(float(valid.sum()) * pixel_m**2 / 1_000_000, 3),
        "relief_p95_minus_p05_m": round(float(np.percentile(elev, 95) - np.percentile(elev, 5)), 2),
        "mean_slope_degrees": round(float(slope_values.mean()), 3),
        "p95_slope_degrees": round(float(np.percentile(slope_values, 95)), 3),
        "mean_3x3_elevation_std_m": round(float(rough_values.mean()), 2),
        "fraction_slope_le_5deg": round(float(np.mean(slope_values <= 5)), 4),
        "fraction_slope_le_8deg": round(float(np.mean(slope_values <= 8)), 4),
    }


def main() -> None:
    outer = zipfile.ZipFile(ARCHIVE)
    nested_name = next(name for name in outer.namelist() if name.endswith("Landing_Sites.zip"))
    archive_bytes = io.BytesIO(outer.read(nested_name))
    inner = zipfile.ZipFile(archive_bytes)

    zones = reader_from_zip(inner, "ExplorationArea_2km")
    points = reader_from_zip(inner, "LandingSites")
    zone_index = next(i for i, rec in enumerate(zones.records()) if rec["Name"] == "SP01")
    point_index = next(i for i, rec in enumerate(points.records()) if rec["Name"] == "SP01")
    source_wkt = inner.read("ExplorationArea_2km.prj").decode("utf-8")
    source_shape = zones.shape(zone_index).__geo_interface__
    source_point = points.shape(point_index).__geo_interface__

    with rasterio.open(DEM_FILE) as src:
        transform = src.transform
        dem = src.read(1, masked=True).filled(np.nan)
        zone_geom = transform_geom(source_wkt, src.crs, source_shape)
        point_geom = transform_geom(source_wkt, src.crs, source_point)
        zone_mask = geometry_mask(
            [zone_geom], out_shape=dem.shape, transform=transform, invert=True, all_touched=False
        )
        col, row = (~transform) * tuple(point_geom["coordinates"])
        rows, cols = np.indices(dem.shape)
        xs = transform.c + (cols + 0.5) * transform.a
        ys = transform.f + (rows + 0.5) * transform.e
        distance = np.hypot(xs - point_geom["coordinates"][0], ys - point_geom["coordinates"][1])
        adjacent_mask = (distance >= 2_000) & (distance < 4_000) & ~zone_mask
        pixel_m = abs(transform.a)
        bounds = [round(v, 2) for v in src.bounds]
        dem_crs = src.crs

    hls_mask_info = {}
    hls_suitable_on_dem_grid = np.zeros(dem.shape, dtype=np.uint8)
    nested = zipfile.ZipFile(archive_bytes)
    hls_name = next(
        name for name in nested.namelist()
        if name.startswith("HLS_LandingAreas_") and name.endswith(".tif")
    )
    with tempfile.TemporaryDirectory(prefix="moonrise_hls_") as tmp_dir:
        hls_path = Path(tmp_dir) / "hls_landing_areas.tif"
        with nested.open(hls_name) as source, hls_path.open("wb") as target:
            shutil.copyfileobj(source, target)
        with rasterio.open(hls_path) as hls:
            hls_geom = transform_geom(source_wkt, hls.crs, source_shape)
            hls_bounds = rasterio.features.bounds(hls_geom)
            hls_window = from_bounds(*hls_bounds, transform=hls.transform).round_offsets().round_lengths()
            hls_values = hls.read(1, window=hls_window, boundless=True)
            hls_transform = rasterio.windows.transform(hls_window, hls.transform)
            hls_zone_mask = geometry_mask(
                [hls_geom], out_shape=hls_values.shape, transform=hls_transform,
                invert=True, all_touched=False,
            )
            eligible = hls_zone_mask & (hls_values > 0)
            zone_n = int(hls_zone_mask.sum())
            eligible_n = int(eligible.sum())
            hls_mask_info = {
                "source_raster": hls_name,
                "interpretation": "Published area satisfying HLS landing-slope and 100 m buffer criteria; positive raster cells denote included suitable area, zero cells are outside the suitable area.",
                "pixel_size_m": [round(abs(hls.transform.a), 2), round(abs(hls.transform.e), 2)],
                "cells_in_exploration_zone": zone_n,
                "suitable_cells_in_exploration_zone": eligible_n,
                "suitable_area_km2": round(eligible_n * abs(hls.transform.a * hls.transform.e) / 1_000_000, 3),
                "suitable_fraction_of_exploration_zone": round(eligible_n / zone_n, 4) if zone_n else None,
            }
            reproject(
                source=(hls_values > 0).astype(np.uint8),
                destination=hls_suitable_on_dem_grid,
                src_transform=hls_transform,
                src_crs=hls.crs,
                dst_transform=transform,
                dst_crs=dem_crs,
                src_nodata=0,
                dst_nodata=0,
                resampling=Resampling.nearest,
            )

    result = {
        "status": "published_operational_zone_vs_adjacent_reference",
        "source": {
            "archive": "Wueller et al. (2026), Zenodo 10.5281/zenodo.17084058",
            "archive_url": "https://zenodo.org/records/17084058",
            "feature": "SP01 ExplorationArea_2km polygon; published 2 km astronaut EVA exploration radius",
            "terrain": "NASA GSFC PGDA LDEM_80S_20MPP_ADJ, clipped 20 m LOLA DEM",
        },
        "target": {"region": "Slater Plain", "site": "SP01", "latitude": -87.4783, "longitude": 124.521},
        "definitions": {
            "operational_zone": "Published SP01 2 km exploration polygon (not the full Slater Plain boundary).",
            "adjacent_reference": "Annulus 2–4 km from the published SP01 point, outside the operational polygon by construction.",
            "terrain_resolution_m": pixel_m,
            "slope_cutoffs": "Descriptive fractions from 20 m DEM-derived slope; not the paper's exact buffered HLS suitability mask.",
        },
        "operational_zone_polygon_area_km2": round(polygon_area_km2(zone_geom), 3),
        "published_hls_suitability": hls_mask_info,
        "dem_bounds_projected_m": bounds,
        "operational_zone": summary(dem, zone_mask, pixel_m),
        "published_hls_suitable_pixels": summary(
            dem, (hls_suitable_on_dem_grid > 0) & zone_mask, pixel_m
        ),
        "adjacent_2_to_4km_ring": summary(dem, adjacent_mask, pixel_m),
        "limitations": [
            "The published polygon is the 2 km walking/EVA exploration buffer around SP01, not a mapped geologic boundary of Slater Plain.",
            "The 2–4 km annulus is a project-defined local reference, not an official NASA or USGS region.",
            "LOLA 20 m posting includes interpolation and cannot resolve all small craters or boulders; the 5 m LOLA mosaic and NAC imagery are needed for finer hazards.",
            "This local Moon-to-Moon contrast does not change the cross-planet score rankings, which require matched Earth data and scale.",
        ],
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    # Produce a simple overview with operational zone and adjacent ring visible.
    from PIL import Image, ImageDraw

    lo, hi = np.nanpercentile(dem, (2, 98))
    gray = np.clip((dem - lo) / (hi - lo) * 255, 0, 255).astype(np.uint8)
    rgb = np.repeat(gray[:, :, None], 3, axis=2)
    rgb[adjacent_mask] = (rgb[adjacent_mask] * 0.55 + np.array([40, 120, 240]) * 0.45).astype(np.uint8)
    rgb[zone_mask] = (rgb[zone_mask] * 0.55 + np.array([255, 120, 45]) * 0.45).astype(np.uint8)
    suitable_inside = (hls_suitable_on_dem_grid > 0) & zone_mask
    rgb[suitable_inside] = (rgb[suitable_inside] * 0.25 + np.array([70, 230, 130]) * 0.75).astype(np.uint8)
    image = Image.fromarray(rgb, "RGB")
    draw = ImageDraw.Draw(image)
    pc, pr = (~transform) * tuple(point_geom["coordinates"])
    draw.ellipse((pc - 5, pr - 5, pc + 5, pr + 5), fill=(255, 255, 0), outline=(0, 0, 0), width=2)
    draw.rectangle((12, 12, 355, 92), fill=(20, 25, 30), outline=(230, 230, 230), width=1)
    draw.rectangle((22, 24, 40, 40), fill=(255, 145, 70))
    draw.text((48, 25), "SP01 2 km exploration zone", fill=(255, 255, 255))
    draw.rectangle((22, 47, 40, 63), fill=(70, 230, 130))
    draw.text((48, 48), "Published HLS-suitable area", fill=(255, 255, 255))
    draw.rectangle((22, 70, 40, 86), fill=(40, 120, 240))
    draw.text((48, 71), "Adjacent 2-4 km reference", fill=(255, 255, 255))
    image.save(MAP)
    print(json.dumps({
        "summary": str(OUT),
        "map": str(MAP),
        "published_hls_suitability": hls_mask_info,
        "operational_zone": result["operational_zone"],
        "published_suitable_terrain": result["published_hls_suitable_pixels"],
        "adjacent": result["adjacent_2_to_4km_ring"],
    }, indent=2))


if __name__ == "__main__":
    main()
