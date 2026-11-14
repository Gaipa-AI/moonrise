"""Extract and summarize a 20 km LOLA 20 m window around Artemis site SP01.

Requires rasterio and network access for NASA's cloud-optimized GeoTIFF. The
output crop is small compared with the 2.6 GB parent mosaic and is written locally.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window


ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "data" / "processed"
SOURCE = "https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_80S_20MPP_ADJ.TIF"
SITE_LAT = -87.478
SITE_LON = 124.521
MOON_RADIUS_M = 1_737_400.0
HALF_WIDTH_M = 10_000.0


def relief(arr: np.ndarray) -> float:
    valid = arr[np.isfinite(arr)]
    return float(np.percentile(valid, 95) - np.percentile(valid, 5))


def block_mean(arr: np.ndarray, factor: int) -> np.ndarray:
    h = (arr.shape[0] // factor) * factor
    w = (arr.shape[1] // factor) * factor
    view = arr[:h, :w].reshape(h // factor, factor, w // factor, factor)
    with np.errstate(invalid="ignore"):
        return np.nanmean(view, axis=(1, 3))


def metrics(arr: np.ndarray, pixel_m: float) -> dict[str, float | int]:
    valid = np.isfinite(arr)
    filled = arr.copy()
    if not valid.all():
        filled[~valid] = float(np.nanmedian(arr))
    gy, gx = np.gradient(filled, pixel_m)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    slope = slope[1:-1, 1:-1]
    local_std = np.lib.stride_tricks.sliding_window_view(filled, (3, 3)).std(axis=(-2, -1))
    return {
        "pixels": int(valid.sum()),
        "valid_cell_fraction": round(float(valid.mean()), 6),
        "relief_p95_minus_p05_m": round(relief(arr), 2),
        "mean_slope_degrees": round(float(slope.mean()), 3),
        "mean_3x3_elevation_std_m": round(float(local_std.mean()), 2),
    }


def main() -> None:
    # Lunar polar stereographic: longitude 0 is at the top of the map.
    rho = 2 * MOON_RADIUS_M * math.tan(math.radians((90 + SITE_LAT) / 2))
    center_x = rho * math.sin(math.radians(SITE_LON))
    center_y = rho * math.cos(math.radians(SITE_LON))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pixel_size_m = 20
    crop_path = OUT_DIR / "slater_sp01_lola_20m_20km.tif"

    if crop_path.exists():
        with rasterio.open(crop_path) as crop:
            dem = crop.read(1, masked=True).filled(np.nan)
    else:
        with rasterio.Env(
            GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
            CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
            CPL_VSIL_CURL_CHUNK_SIZE="1048576",
            CPL_VSIL_CURL_CACHE_SIZE="268435456",
            GDAL_CACHEMAX=128,
        ):
            with rasterio.open("/vsicurl/" + SOURCE) as src:
                col, row = (~src.transform) * (center_x, center_y)
                size = int(round((2 * HALF_WIDTH_M) / abs(src.transform.a)))
                window = Window(round(col - size / 2), round(row - size / 2), size, size)
                dem = src.read(1, window=window, boundless=True, masked=True).filled(np.nan)
                profile = src.profile.copy()
                profile.update(
                    width=size,
                    height=size,
                    transform=rasterio.windows.transform(window, src.transform),
                    compress="deflate",
                    tiled=True,
                    blockxsize=256,
                    blockysize=256,
                    nodata=np.nan,
                )

        with rasterio.open(crop_path, "w", **profile) as dst:
            dst.write(dem.astype(np.float32), 1)

    scales = {}
    for factor in (1, 2, 5, 25):
        sampled = dem if factor == 1 else block_mean(dem, factor)
        scales[f"{pixel_size_m * factor}m_grid"] = metrics(sampled, pixel_size_m * factor)

    result = {
        "product": "NASA GSFC PGDA A New View of the Lunar South Pole from LOLA",
        "source_url": SOURCE,
        "site": {"name": "Slater Plain SP01", "latitude": SITE_LAT, "longitude": SITE_LON},
        "crop": {"width_m": 20_000, "height_m": 20_000, "pixel_m": pixel_size_m, "file": str(crop_path)},
        "projection_center_xy_m": [round(center_x, 1), round(center_y, 1)],
        "scales": scales,
        "limitations": [
            "This is regional context centered on representative point SP01, not a surveyed Slater Plain site boundary.",
            "The LOLA 20 m grid is interpolated between laser tracks; nominal pixel spacing is not equivalent to independent 20 m measurements.",
            "Compare Earth analogs at matched coarser scales and with resolution caveats.",
            "Terrain similarity scores remain screening indicators, not learned-model probabilities or training suitability certifications.",
        ],
    }
    result_path = OUT_DIR / "slater_sp01_20m_summary.json"
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"crop": str(crop_path), "result": str(result_path), "scales": scales}, indent=2))


if __name__ == "__main__":
    main()
