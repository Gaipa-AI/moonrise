"""Score the uploaded Earth samples against the new 20 m LOLA product.

The 20 m lunar crop is aggregated to 500 m before comparing with the existing
Earth/Mars regional summaries so the comparison support stays approximately
matched. These remain exploratory scores, not ML predictions.
"""

from __future__ import annotations

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
BASE = HERE / "results" / "terrain_summary_v1.json"
HIGH_RES = HERE / "data" / "processed" / "slater_sp01_20m_summary.json"
OUTPUT = HERE / "results" / "terrain_comparison_v3.json"
METRICS = (
    ("relief_p95_minus_p05_m", "p95-p05 local relief", "m"),
    ("mean_slope_degrees", "Mean slope", "degrees"),
    ("mean_3x3_elevation_std_m", "3x3-cell elevation standard deviation", "m"),
)


def main() -> None:
    summary = json.loads(BASE.read_text(encoding="utf-8"))
    highres = json.loads(HIGH_RES.read_text(encoding="utf-8"))
    moon = {
        **highres["scales"]["500m_grid"],
        "site": "Slater Plain (representative candidate point SP01)",
    }
    all_rankings = {}
    for body in ("moon", "mars"):
        target = moon if body == "moon" else summary[body]
        rows = []
        for earth in summary["earth"]:
            feature_rows = []
            for key, label, unit in METRICS:
                target_value = float(target[key])
                earth_value = float(earth[key])
                difference = abs(earth_value - target_value)
                feature_rows.append({
                    "feature": label,
                    "earth_value": earth_value,
                    "target_value": target_value,
                    "absolute_difference": round(difference, 4),
                    "unit": unit,
                    "similarity_pct_by_scale_factor": {
                        str(factor): round(100 * max(0.0, 1 - difference / (factor * abs(target_value))), 2)
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
            "name": "relative_linear_terrain_similarity_v3",
            "formula_per_feature": "max(0, 1 - abs(Earth - target) / (scale_factor * abs(target)))",
            "aggregate": "unweighted mean of the three terrain feature similarities",
            "default_scale_factor": 2.0,
            "sensitivity_scale_factors": [1.0, 1.5, 2.0, 3.0],
            "features": [label for _, label, _ in METRICS],
            "meaning": "The feature reaches zero at a difference of twice the target value under the default setting.",
        },
        "earth_source": "NASA SRTMGL1 V003, existing roughly 0.5 km regional summaries",
        "lunar_source": "NASA GSFC PGDA LOLA LDEM_80S_20MPP_ADJ, 20 m regional crop aggregated to 500 m",
        "mars_source": "MGS MOLA MEGDR 128 pixels/degree, existing Jezero regional summary",
        "analysis_window": "20 km x 20 km centered on SP01 for the Moon, Earth candidate centers and Jezero; approximately 0.5 km analysis cells.",
        "caveats": [
            "This is not a trained machine-learning model; there are no labeled analog/non-analog training data.",
            "The lunar 20 m grid has interpolated LOLA cells and does not imply 20 m effective measurement resolution.",
            "The ROI is centered on SP01 and is not the official Slater Plain candidate-region polygon.",
            "This compares terrain only, not mineralogy, temperature, dust, water/ice, radiation, pressure, gravity, or operational safety.",
            "The three-feature equal-weight score and scale factor are exploratory; the candidate Earth sample is small and preselected.",
            "A score is not a probability, site equivalence claim, or astronaut-training suitability certification.",
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
