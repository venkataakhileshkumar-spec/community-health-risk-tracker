"""
Read-side endpoints for risk scores: per-community history, latest snapshot
across all communities (for a leaderboard/dashboard), and simple trend
detection between the two most recent reporting periods.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/api/risk", tags=["risk"])


@router.get("/communities/{community_id}", response_model=List[schemas.RiskScoreOut])
def get_community_risk_history(community_id: int, db: Session = Depends(get_db)):
    community = db.query(models.Community).get(community_id)
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")
    return (
        db.query(models.RiskScore)
        .filter_by(community_id=community_id)
        .order_by(models.RiskScore.reporting_period)
        .all()
    )


@router.get("/communities/{community_id}/latest", response_model=schemas.RiskScoreDetail)
def get_latest_score(community_id: int, db: Session = Depends(get_db)):
    community = db.query(models.Community).get(community_id)
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")

    latest = (
        db.query(models.RiskScore)
        .filter_by(community_id=community_id)
        .order_by(models.RiskScore.reporting_period.desc())
        .first()
    )
    if not latest:
        raise HTTPException(status_code=404, detail="No risk scores computed for this community yet")

    latest_indicator = (
        db.query(models.HealthIndicator)
        .filter_by(community_id=community_id, reporting_period=latest.reporting_period)
        .first()
    )

    from app.risk_engine import Indicators, compute_risk

    contributing = []
    if latest_indicator:
        result = compute_risk(
            Indicators(
                diabetes_prevalence_pct=latest_indicator.diabetes_prevalence_pct,
                hypertension_prevalence_pct=latest_indicator.hypertension_prevalence_pct,
                obesity_prevalence_pct=latest_indicator.obesity_prevalence_pct,
                poverty_rate_pct=latest_indicator.poverty_rate_pct,
                uninsured_rate_pct=latest_indicator.uninsured_rate_pct,
                food_desert_index=latest_indicator.food_desert_index,
                providers_per_10k=latest_indicator.providers_per_10k,
                avg_distance_to_care_miles=latest_indicator.avg_distance_to_care_miles,
                air_quality_index=latest_indicator.air_quality_index,
            )
        )
        contributing = result.contributing_factors

    return schemas.RiskScoreDetail(
        **schemas.RiskScoreOut.model_validate(latest).model_dump(),
        community_name=community.name,
        contributing_factors=contributing,
    )


@router.get("/leaderboard", response_model=List[schemas.CommunityRiskSummary])
def get_leaderboard(db: Session = Depends(get_db)):
    """
    Returns every community with its most recent risk score, sorted highest
    risk first, along with a simple trend indicator vs. the prior period.
    """
    communities = db.query(models.Community).all()
    summaries: List[schemas.CommunityRiskSummary] = []

    for community in communities:
        scores = (
            db.query(models.RiskScore)
            .filter_by(community_id=community.id)
            .order_by(models.RiskScore.reporting_period.desc())
            .limit(2)
            .all()
        )

        if not scores:
            summaries.append(
                schemas.CommunityRiskSummary(
                    community_id=community.id,
                    community_name=community.name,
                    state=community.state,
                    latest_period=None,
                    latest_score=None,
                    latest_tier=None,
                    trend=None,
                )
            )
            continue

        latest = scores[0]
        trend = None
        if len(scores) == 2:
            delta = latest.composite_score - scores[1].composite_score
            if delta > 1.5:
                trend = "worsening"
            elif delta < -1.5:
                trend = "improving"
            else:
                trend = "stable"

        summaries.append(
            schemas.CommunityRiskSummary(
                community_id=community.id,
                community_name=community.name,
                state=community.state,
                latest_period=latest.reporting_period,
                latest_score=latest.composite_score,
                latest_tier=latest.risk_tier,
                trend=trend,
            )
        )

    summaries.sort(key=lambda s: (s.latest_score is None, -(s.latest_score or 0)))
    return summaries
