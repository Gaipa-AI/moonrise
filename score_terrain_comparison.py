"""Build a provisional, auditable Earth-vs-Mars terrain score table."""

from __future__ import annotations

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
INPUT = HERE / "results" / "terrain_summary_v1.json"
OUTPUT = HERE / "results" / "terrain_comparison_v2.json"
METRICS = (
    ("relief_p95_minus_p05_m", "p95-p05 local relief", "m"),
    ("mean_slope_degrees", "Mean slope", "degrees"),
    ("mean_3x3_elevation_std_m", "3x3-cell elevation standard deviation", "m"),
)


def main() -> None:
    summary = json.loads(INPUT.read_text(encoding="utf-8"))
    all_rankings = {}
    for body in ("moon", "mars"):
        target = summary[body]
        rows = []
        for earth in summary["earth"]:
            feature_rows = []
            for key, label, unit in METRICS:
                target_value = float(target[key])
                earth_value = float(earth[key])
                difference = abs(earth_value - target_value)
                target_scale = abs(target_value)
                feature_rows.append({
                    "feature": label,
                    "earth_value": earth_value,
                    "target_value": target_value,
                    "absolute_difference": round(difference, 4),
                    "unit": unit,
                    "similarity_pct_by_scale_factor": {
                        str(factor): round(100 * max(0.0, 1 - difference / (factor * target_scale)), 2)
                        for factor in (1.0, 1.5, 2.0, 3.0)
                    },
                })
            scores = {
                str(factor): round(
                    sum(feature["similarity_pct_by_scale_factor"][str(factor)] for feature in feature_rows)
                    / len(feature_rows), 2,
                )
                for factor in (1.0, 1.5, 2.0, 3.0)
            }
            rows.append({
                "earth_site": earth["site"],
                "target_body": body,
                "target_region": target["site"],
                "terrain_similarity_pct_by_scale_factor": scores,
                "default_scale_factor": 2.0,
                "default_score_pct": scores["2.0"],
                "features": feature_rows,
            })
        rows.sort(key=lambda row: row["default_score_pct"], reverse=True)
        all_rankings[body] = rows
    result = {
        "schema_version": "1.0",
        "status": "provisional_data_derived_terrain_similarity_not_probability_or_ml_prediction",
        "model": {
            "name": "relative_linear_terrain_similarity_v2",
            "formula_per_feature": "max(0, 1 - abs(Earth - Mars) / (scale_factor * abs(Mars)))",
            "aggregate": "unweighted mean of the three terrain feature similarities",
            "default_scale_factor": 2.0,
            "sensitivity_scale_factors": [1.0, 1.5, 2.0, 3.0],
            "features": [label for _, label, _ in METRICS],
            "meaning": "The feature reaches zero at a difference of twice the Mars reference value under the default setting. The score is descriptive and depends on this explicit scaling choice.",
        },
        "earth_sources": ["NASA SRTMGL1 V003"],
        "planetary_sources": {
            "moon": "LRO LOLA GDR LDEM_75S_240M, 20 km window centered at Slater Plain SP01 representative point",
            "mars": "MGS MOLA MEGDR 128 pixels/degree, Jezero ROI",
        },
        "analysis_window": "Approximately 20 km x 20 km for each Earth site and planetary reference; all elevation grids aggregated or retained at approximately 0.5 km support.",
        "caveats": [
            "This is not a trained machine-learning model: no labeled analog/non-analog training data are available.",
            "It measures terrain only; it does not score mineralogy, temperature, wind/dust, water/ice, radiation, pressure, gravity, biology, access, or operational safety.",
            "The unweighted three-feature aggregate and scale factor are provisional research choices, not empirically calibrated parameters.",
            "MOLA has interpolated bins and relatively sparse equatorial tracks; the ROI is regional context, not rover-scale terrain.",
            "The Slater Plain window is centered on one published representative candidate point, not the full landing-region polygon.",
            "The 240 m LOLA source is too coarse to fully resolve small craters and boulders in the crater-strewn plain.",
            "A high terrain score indicates matching summaries at this chosen scale, not site equivalence or astronaut-training suitability.",
        ],
        "rankings_by_target": all_rankings,
    }
    OUTPUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    for body, rows in all_rankings.items():
        print(body)
        for row in rows:
            print(row["earth_site"], row["default_score_pct"], row["terrain_similarity_pct_by_scale_factor"])
    print(OUTPUT)


if __name__ == "__main__":
    main()
