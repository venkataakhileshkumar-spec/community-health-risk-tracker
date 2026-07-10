"""
Risk Engine
===========

Computes a composite Community Health Risk Score (0-100, higher = more risk)
from four weighted subscores:

    1. Chronic Disease Burden      (35%)
    2. Social Determinants of Health (30%)
    3. Healthcare Access            (25%)
    4. Environmental Exposure       (10%)

Each subscore is itself a normalized 0-100 value built from raw indicators.
Weights and normalization bounds are intentionally explicit and easy to tune
as better local reference data becomes available (e.g. CDC PLACES benchmarks,
county-level ACS estimates, EPA AQI thresholds).

This is a transparent, rules-based model chosen deliberately over a black-box
ML model: for population health resource allocation, stakeholders need to be
able to see exactly why a community was flagged.
"""
from dataclasses import dataclass
from typing import List, Tuple

# Subscore weights - must sum to 1.0
WEIGHT_CHRONIC_DISEASE = 0.35
WEIGHT_SOCIAL_DETERMINANTS = 0.30
WEIGHT_ACCESS = 0.25
WEIGHT_ENVIRONMENTAL = 0.10

# Normalization bounds: (floor, ceiling) mapping raw indicator range -> 0-100
# Floor = value considered "no added risk", ceiling = value considered "max risk"
BOUNDS = {
    "diabetes_prevalence_pct": (4.0, 16.0),
    "hypertension_prevalence_pct": (20.0, 50.0),
    "obesity_prevalence_pct": (15.0, 45.0),
    "poverty_rate_pct": (5.0, 35.0),
    "uninsured_rate_pct": (2.0, 25.0),
    "food_desert_index": (0.0, 100.0),
    "providers_per_10k": (30.0, 5.0),  # inverted: MORE providers = LESS risk
    "avg_distance_to_care_miles": (2.0, 40.0),
    "air_quality_index": (25.0, 200.0),
}

RISK_TIERS: List[Tuple[float, str]] = [
    (25.0, "Low"),
    (50.0, "Moderate"),
    (75.0, "High"),
    (100.01, "Critical"),
]


def _normalize(value: float, floor: float, ceiling: float) -> float:
    """
    Map a raw indicator value onto a 0-100 risk scale given a floor (no-risk
    reference point) and ceiling (max-risk reference point). Handles both
    ascending (floor < ceiling) and inverted (floor > ceiling) indicators,
    and clamps output to [0, 100].
    """
    if floor == ceiling:
        return 0.0
    pct = (value - floor) / (ceiling - floor)
    return max(0.0, min(100.0, pct * 100.0))


@dataclass
class Indicators:
    diabetes_prevalence_pct: float
    hypertension_prevalence_pct: float
    obesity_prevalence_pct: float
    poverty_rate_pct: float
    uninsured_rate_pct: float
    food_desert_index: float
    providers_per_10k: float
    avg_distance_to_care_miles: float
    air_quality_index: float


@dataclass
class RiskResult:
    composite_score: float
    risk_tier: str
    chronic_disease_subscore: float
    social_determinants_subscore: float
    access_subscore: float
    environmental_subscore: float
    contributing_factors: List[str]


def _tier_for_score(score: float) -> str:
    for threshold, tier in RISK_TIERS:
        if score < threshold:
            return tier
    return RISK_TIERS[-1][1]


def _top_contributing_factors(normalized: dict, top_n: int = 3) -> List[str]:
    """Return the top_n indicators contributing the most risk, human-readable."""
    labeled = {
        "diabetes_prevalence_pct": "Elevated diabetes prevalence",
        "hypertension_prevalence_pct": "Elevated hypertension prevalence",
        "obesity_prevalence_pct": "Elevated obesity prevalence",
        "poverty_rate_pct": "High poverty rate",
        "uninsured_rate_pct": "High uninsured rate",
        "food_desert_index": "Limited food access (food desert index)",
        "providers_per_10k": "Low provider density",
        "avg_distance_to_care_miles": "Long average distance to care",
        "air_quality_index": "Poor air quality",
    }
    ranked = sorted(normalized.items(), key=lambda kv: kv[1], reverse=True)
    return [labeled[key] for key, score in ranked[:top_n] if score > 40.0]


def compute_risk(indicators: Indicators) -> RiskResult:
    """
    Compute the composite risk score and subscores for a single set of
    community health indicators.
    """
    normalized = {
        field: _normalize(getattr(indicators, field), *BOUNDS[field])
        for field in BOUNDS
    }

    chronic_disease_subscore = round(
        (
            normalized["diabetes_prevalence_pct"]
            + normalized["hypertension_prevalence_pct"]
            + normalized["obesity_prevalence_pct"]
        )
        / 3,
        2,
    )

    social_determinants_subscore = round(
        (
            normalized["poverty_rate_pct"]
            + normalized["uninsured_rate_pct"]
            + normalized["food_desert_index"]
        )
        / 3,
        2,
    )

    access_subscore = round(
        (normalized["providers_per_10k"] + normalized["avg_distance_to_care_miles"]) / 2,
        2,
    )

    environmental_subscore = round(normalized["air_quality_index"], 2)

    composite = round(
        chronic_disease_subscore * WEIGHT_CHRONIC_DISEASE
        + social_determinants_subscore * WEIGHT_SOCIAL_DETERMINANTS
        + access_subscore * WEIGHT_ACCESS
        + environmental_subscore * WEIGHT_ENVIRONMENTAL,
        2,
    )

    return RiskResult(
        composite_score=composite,
        risk_tier=_tier_for_score(composite),
        chronic_disease_subscore=chronic_disease_subscore,
        social_determinants_subscore=social_determinants_subscore,
        access_subscore=access_subscore,
        environmental_subscore=environmental_subscore,
        contributing_factors=_top_contributing_factors(normalized),
    )
