"""Create comparable terrain summaries from the first uploaded raster bundle.

Uses only NumPy and Pillow. It keeps source rasters unchanged and writes a small
JSON summary beside this script. This is a measured feature extraction step,
not a trained model or a final analog score.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
EARTH = ROOT / "Earth_SRTM"
MOON = ROOT / "Moon_LOLA"
MARS = ROOT / "Mars_MOLA"
OUT = Path(__file__).resolve().parent / "results" / "terrain_summary_v1.json"

EARTH_SITES = {
    "Makgadikgadi Pans, Botswana": {
        "file": "S21E025.hgt", "tile": "S21E025", "lat": -20.5, "lon": 25.5,
    },
    "Lake Magadi, Kenya": {
        "file": "S02E036.hgt", "tile": "S02E036", "lat": -1.9, "lon": 36.3,
    },
    "Harrat Khaybar, Saudi Arabia": {
        "file": "N25E039.hgt", "tile": "N25E039", "lat": 25.7, "lon": 39.9,
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def block_mean(values: np.ndarray, rows: int, cols: int) -> np.ndarray:
    h = values.shape[0] // rows * rows
    w = values.shape[1] // cols * cols
    trimmed = values[:h, :w]
    grouped = trimmed.reshape(h // rows, rows, w // cols, cols)
    valid = np.isfinite(grouped)
    sums = np.where(valid, grouped, 0.0).sum(axis=(1, 3))
    counts = valid.sum(axis=(1, 3))
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(counts > 0, sums / counts, np.nan)


def terrain_metrics(
    values: np.ndarray,
    dx_m: float,
    dy_m: float,
    source: dict,
) -> dict:
    finite = np.isfinite(values)
    if np.count_nonzero(finite) < 25:
        raise ValueError(f"Not enough valid elevations in {source.get('source')}")
    filled = values.copy()
    # Derivatives and local roughness require complete 3x3 neighborhoods. Fill
    # only isolated no-data cells for derivative estimation; report coverage.
    if not finite.all():
        fill_value = float(np.nanmedian(values))
        filled[~finite] = fill_value
    gy, gx = np.gradient(filled, dy_m, dx_m)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    neighborhoods = np.lib.stride_tricks.sliding_window_view(filled, (3, 3))
    roughness = neighborhoods.std(axis=(-1, -2))
    return {
        **source,
        "grid_shape_rows_cols": list(values.shape),
        "valid_cell_fraction": round(float(np.mean(finite)), 6),
        "effective_cell_size_m": {"x": round(dx_m, 1), "y": round(dy_m, 1)},
        "relief_p95_minus_p05_m": round(float(np.nanpercentile(values, 95) - np.nanpercentile(values, 5)), 2),
        "mean_slope_degrees": round(float(np.mean(slope[1:-1, 1:-1])), 3),
        "mean_3x3_elevation_std_m": round(float(np.mean(roughness)), 2),
        "elevation_p05_m": round(float(np.nanpercentile(values, 5)), 2),
        "elevation_p50_m": round(float(np.nanpercentile(values, 50)), 2),
        "elevation_p95_m": round(float(np.nanpercentile(values, 95)), 2),
    }


def earth_window(site: dict) -> dict:
    path = EARTH / site["file"]
    expected_bytes = 3601 * 3601 * 2
    if path.stat().st_size != expected_bytes:
        raise ValueError(f"Unexpected SRTM tile size: {path}")
    # HGT tiles are signed big-endian 16-bit samples, north-to-south rows.
    hgt = np.fromfile(path, dtype=">i2").reshape((3601, 3601)).astype(np.float32)
    hgt[hgt == -32768] = np.nan

    lat = site["lat"]
    lon = site["lon"]
    half_lat = 10.0 / 111.132
    half_lon = 10.0 / (111.320 * math.cos(math.radians(lat)))
    south = lat - half_lat
    north = lat + half_lat
    west = lon - half_lon
    east = lon + half_lon
    tile_south = int(site["tile"][1:3]) * (-1 if site["tile"][0] == "S" else 1)
    tile_west = int(site["tile"][4:7]) * (-1 if site["tile"][3] == "W" else 1)
    r0 = max(0, int(math.floor((tile_south + 1 - north) * 3600)))
    r1 = min(3601, int(math.ceil((tile_south + 1 - south) * 3600)) + 1)
    c0 = max(0, int(math.floor((west - tile_west) * 3600)))
    c1 = min(3601, int(math.ceil((east - tile_west) * 3600)) + 1)
    roi = hgt[r0:r1, c0:c1]

    native_y = 111_132.0 / 3600.0
    native_x = 111_320.0 * math.cos(math.radians(lat)) / 3600.0
    factor_y = max(1, round(480.0 / native_y))
    factor_x = max(1, round(480.0 / native_x))
    coarse = block_mean(roi, factor_y, factor_x)
    dx = native_x * factor_x
    dy = native_y * factor_y
    # The HGT file has sample posts at 1 arc-second; the requested window is
    # centered on the candidate coordinates and approximately 20 km square.
    return terrain_metrics(
        coarse, dx, dy,
        {
            "body": "Earth", "site": next(k for k, v in EARTH_SITES.items() if v is site),
            "source": f"NASA SRTMGL1 V003 {site['tile']}",
            "source_sha256": sha256(path),
            "roi_center_lat_lon": [lat, lon],
            "roi_bounds_lat_lon": [round(south, 6), round(west, 6), round(north, 6), round(east, 6)],
            "roi_intended_size_km": [20, 20],
            "native_resolution_arcseconds": 1,
        },
    )


def moon_window() -> dict:
    path = MOON / "ldem_75s_240m.jp2"
    with Image.open(path) as image:
        unsigned = np.asarray(image, dtype=np.uint16)
    # The JP2 decoder exposes the signed PDS sample bit pattern as uint16;
    # subtracting 32768 recovers label values (-15529..14049). The PDS scale
    # is 0.5 m/sample and the constant reference radius cancels in relief/slope.
    values = (unsigned.astype(np.int32) - 32768).astype(np.float32) * 0.5
    expected = (3812, 3812)
    if values.shape != expected:
        raise ValueError(f"Unexpected LOLA raster shape: {values.shape}")
    if int((unsigned.astype(np.int32) - 32768).min()) < -15529 or int((unsigned.astype(np.int32) - 32768).max()) > 14049:
        raise ValueError("LOLA samples do not fit the PDS label range")
    # SP01 is a representative candidate point within the Slater Plain region.
    # PDS polar stereographic coordinates are centered at the pole, with 0E
    # north/up and east longitudes clockwise toward image right.
    lat, lon = -87.478, 124.521
    radius = 1_737_400.0
    rho = 2 * radius * math.tan(math.radians((90 + lat) / 2))
    x = rho * math.sin(math.radians(lon))
    y = -rho * math.cos(math.radians(lon))
    center = values.shape[0] // 2
    center_col = round(center + x / 240.0)
    center_row = round(center + y / 240.0)
    # A ~20 km square at 240 m/pixel centered on representative Slater Plain
    # candidate point SP01; this is not the full candidate-region boundary.
    side = round(20_000 / 240)
    r0, c0 = center_row - side // 2, center_col - side // 2
    roi = values[r0:r0 + side, c0:c0 + side]
    coarse = block_mean(roi, 2, 2)
    return terrain_metrics(
        coarse, 480.0, 480.0,
        {
            "body": "Moon", "site": "Slater Plain (representative candidate point SP01)",
            "source": "LRO LOLA GDR LDEM_75S_240M V2.1",
            "source_sha256": sha256(path),
            "roi_center_lat_lon": [lat, lon],
            "roi_intended_size_km": [20, 20],
            "native_resolution_m": 240,
            "vertical_reference": "sample * 0.5 m relative to 1,737,400 km reference radius; constant removed for terrain metrics",
        },
    )


def mars_window() -> dict:
    path = MARS / "megt44n000hb.img"
    expected_bytes = 5632 * 11520 * 2
    if path.stat().st_size != expected_bytes:
        raise ValueError(f"Unexpected MOLA tile size: {path}")
    # MOLA PDS product: signed big-endian 16-bit meter elevations.
    dem = np.fromfile(path, dtype=">i2").reshape((5632, 11520)).astype(np.float32)
    dem[dem == 0] = np.nan  # PDS ENVI header marks zero as ignored.

    lat, lon = 18.4446, 77.4509  # Perseverance landing coordinate in Jezero crater.
    lat_km_per_degree = 2 * math.pi * 3396.0 / 360.0
    half_lat = 10.0 / lat_km_per_degree
    half_lon = 10.0 / (lat_km_per_degree * math.cos(math.radians(lat)))
    north, south = lat + half_lat, lat - half_lat
    west, east = lon - half_lon, lon + half_lon
    r0 = max(0, int(math.floor((44.0 - north) * 128)))
    r1 = min(5632, int(math.ceil((44.0 - south) * 128)) + 1)
    c0 = max(0, int(math.floor(west * 128)))
    c1 = min(11520, int(math.ceil(east * 128)) + 1)
    roi = dem[r0:r1, c0:c1]
    dx = 2 * math.pi * 3396_000 / (360 * 128) * math.cos(math.radians(lat))
    dy = 2 * math.pi * 3396_000 / (360 * 128)
    return terrain_metrics(
        roi, dx, dy,
        {
            "body": "Mars", "site": "Jezero crater / Perseverance landing region",
            "source": "MGS MOLA MEGDR 128 ppd tile megt44n000hb",
            "source_sha256": sha256(path),
            "roi_center_lat_lon": [lat, lon],
            "roi_bounds_lat_lon": [round(south, 6), round(west, 6), round(north, 6), round(east, 6)],
            "roi_intended_size_km": [20, 20],
            "native_resolution_m": {"x": round(dx, 1), "y": round(dy, 1)},
            "vertical_reference": "MOLA topography relative to Mars areoid",
        },
    )


def main() -> None:
    earth_results = [earth_window(site) for site in EARTH_SITES.values()]
    results = {
        "schema_version": "1.0",
        "status": "measured_terrain_features_not_final_similarity_scores",
        "method": {
            "feature_family": "regional topography",
            "window": "approximately 20 km by 20 km per site",
            "analysis_scale": "Earth DEM block-aggregated to approximately 0.5 km; LOLA aggregated to 0.48 km; MOLA retained at approximately 0.46 km",
            "features": ["p95-p05 elevation relief", "mean slope", "mean 3x3 elevation standard deviation"],
            "limitations": [
                "This is a transparent terrain feature extraction, not a trained ML model or final score.",
                "Terrain similarity does not imply similarity in geology, temperature, atmosphere, radiation, gravity, or field-training suitability.",
                "The LOLA ROI is centered on Slater Plain representative point SP01, not the official Artemis candidate-region polygon.",
                "MOLA zeros are masked as indicated by the supplied ENVI header; interpolated MOLA cells remain in the sample.",
                "Earth windows are centered on the candidate coordinates and are not field-verified boundaries.",
            ],
        },
        "earth": earth_results,
        "moon": moon_window(),
        "mars": mars_window(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(OUT)
    for feature in earth_results + [results["moon"], results["mars"]]:
        print(
            feature["body"], feature["site"],
            "relief_p95_p05_m=", feature["relief_p95_minus_p05_m"],
            "mean_slope_deg=", feature["mean_slope_degrees"],
            "roughness_m=", feature["mean_3x3_elevation_std_m"],
            "valid=", feature["valid_cell_fraction"],
        )


if __name__ == "__main__":
    main()
