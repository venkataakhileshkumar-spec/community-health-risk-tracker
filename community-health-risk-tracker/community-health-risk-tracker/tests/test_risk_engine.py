"""
Unit tests for the composite risk scoring engine. These pin down the
normalization and weighting behavior so future tuning doesn't silently
change results.
"""
import pytest
from app.risk_engine import Indicators, compute_risk, _normalize, _tier_for_score


def make_indicators(**overrides):
    base = dict(
        diabetes_prevalence_pct=8.0,
        hypertension_prevalence_pct=28.0,
        obesity_prevalence_pct=25.0,
        poverty_rate_pct=12.0,
        uninsured_rate_pct=8.0,
        food_desert_index=30.0,
        providers_per_10k=15.0,
        avg_distance_to_care_miles=10.0,
        air_quality_index=50.0,
    )
    base.update(overrides)
    return Indicators(**base)


def test_normalize_ascending_within_range():
    assert _normalize(10.0, 0.0, 20.0) == 50.0


def test_normalize_clamps_below_floor():
    assert _normalize(-5.0, 0.0, 20.0) == 0.0


def test_normalize_clamps_above_ceiling():
    assert _normalize(25.0, 0.0, 20.0) == 100.0


def test_normalize_inverted_range():
    # providers_per_10k: floor=30 (no risk), ceiling=5 (max risk)
    # Fewer providers => higher risk
    low_providers = _normalize(5.0, 30.0, 5.0)
    high_providers = _normalize(30.0, 30.0, 5.0)
    assert low_providers == 100.0
    assert high_providers == 0.0


def test_best_case_scores_low():
    """Best-case indicators (all at healthy floor values) should score near 0."""
    indicators = make_indicators(
        diabetes_prevalence_pct=4.0,
        hypertension_prevalence_pct=20.0,
        obesity_prevalence_pct=15.0,
        poverty_rate_pct=5.0,
        uninsured_rate_pct=2.0,
        food_desert_index=0.0,
        providers_per_10k=30.0,
        avg_distance_to_care_miles=2.0,
        air_quality_index=25.0,
    )
    result = compute_risk(indicators)
    assert result.composite_score < 5.0
    assert result.risk_tier == "Low"


def test_worst_case_scores_critical():
    """Worst-case indicators (all at max-risk ceiling) should score near 100."""
    indicators = make_indicators(
        diabetes_prevalence_pct=16.0,
        hypertension_prevalence_pct=50.0,
        obesity_prevalence_pct=45.0,
        poverty_rate_pct=35.0,
        uninsured_rate_pct=25.0,
        food_desert_index=100.0,
        providers_per_10k=5.0,
        avg_distance_to_care_miles=40.0,
        air_quality_index=200.0,
    )
    result = compute_risk(indicators)
    assert result.composite_score > 95.0
    assert result.risk_tier == "Critical"


def test_subscores_sum_to_composite_via_weights():
    indicators = make_indicators()
    result = compute_risk(indicators)
    expected = round(
        result.chronic_disease_subscore * 0.35
        + result.social_determinants_subscore * 0.30
        + result.access_subscore * 0.25
        + result.environmental_subscore * 0.10,
        2,
    )
    assert result.composite_score == expected


def test_tier_boundaries():
    assert _tier_for_score(0) == "Low"
    assert _tier_for_score(24.9) == "Low"
    assert _tier_for_score(25.0) == "Moderate"
    assert _tier_for_score(50.0) == "High"
    assert _tier_for_score(75.0) == "Critical"
    assert _tier_for_score(100.0) == "Critical"


def test_contributing_factors_identifies_high_risk_indicators():
    indicators = make_indicators(
        diabetes_prevalence_pct=16.0,  # max risk
        poverty_rate_pct=5.0,          # min risk
    )
    result = compute_risk(indicators)
    assert any("diabetes" in f.lower() for f in result.contributing_factors)


def test_contributing_factors_empty_when_all_moderate():
    """When nothing crosses the 40-point threshold, no factors are flagged."""
    indicators = make_indicators(
        diabetes_prevalence_pct=8.0,
        hypertension_prevalence_pct=28.0,
        obesity_prevalence_pct=22.0,
        poverty_rate_pct=10.0,
        uninsured_rate_pct=6.0,
        food_desert_index=15.0,
        providers_per_10k=22.0,
        avg_distance_to_care_miles=6.0,
        air_quality_index=45.0,
    )
    result = compute_risk(indicators)
    assert result.contributing_factors == []
