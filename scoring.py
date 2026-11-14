"""Interpretable feature-distance scoring for planetary analog research.

This module intentionally does not infer scores from imagery or claim a trained
ML model. Inputs must be measurements produced by a documented data pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping


@dataclass(frozen=True)
class FeatureSpec:
    """Definition shared by Earth measurement and target profile.

    ``scale`` is the absolute difference that maps to zero similarity. The
    feature's Earth and target values must use the same unit and definition.
    """

    name: str
    unit: str
    scale: float
    weight: float
    family: str

    def __post_init__(self) -> None:
        if not self.name or not self.unit or not self.family:
            raise ValueError("name, unit, and family must be non-empty")
        if not isfinite(self.scale) or self.scale <= 0:
            raise ValueError("scale must be finite and greater than zero")
        if not isfinite(self.weight) or self.weight < 0:
            raise ValueError("weight must be finite and non-negative")


@dataclass(frozen=True)
class FeatureMatch:
    name: str
    family: str
    earth_value: float
    target_value: float
    unit: str
    similarity: float
    weighted_contribution: float


@dataclass(frozen=True)
class SimilarityResult:
    score: float | None
    coverage: float
    matches: tuple[FeatureMatch, ...]
    missing_features: tuple[str, ...]


def score_features(
    earth: Mapping[str, float | None],
    target: Mapping[str, float | None],
    specs: tuple[FeatureSpec, ...],
) -> SimilarityResult:
    """Return a 0..100 weighted similarity with explicit missing-data coverage.

    Similarity per feature is ``max(0, 1 - abs(earth-target)/scale)``. Only
    features with finite values on both sides contribute; remaining weights are
    renormalized. A result is ``None`` if no positive-weight feature is usable.
    """

    names = [spec.name for spec in specs]
    if len(names) != len(set(names)):
        raise ValueError("feature names must be unique")
    total_weight = sum(spec.weight for spec in specs)
    if total_weight <= 0:
        raise ValueError("at least one feature must have positive weight")

    matches: list[FeatureMatch] = []
    missing: list[str] = []
    observed_weight = 0.0
    weighted_sum = 0.0
    for spec in specs:
        if spec.weight == 0:
            continue
        e = earth.get(spec.name)
        t = target.get(spec.name)
        if e is None or t is None or not isfinite(e) or not isfinite(t):
            missing.append(spec.name)
            continue
        similarity = max(0.0, 1.0 - abs(e - t) / spec.scale)
        observed_weight += spec.weight
        weighted_sum += similarity * spec.weight
        matches.append(
            FeatureMatch(
                name=spec.name,
                family=spec.family,
                earth_value=e,
                target_value=t,
                unit=spec.unit,
                similarity=similarity,
                weighted_contribution=similarity * spec.weight / total_weight,
            )
        )

    score = 100.0 * weighted_sum / observed_weight if observed_weight else None
    coverage = observed_weight / total_weight
    return SimilarityResult(
        score=score,
        coverage=coverage,
        matches=tuple(matches),
        missing_features=tuple(missing),
    )
