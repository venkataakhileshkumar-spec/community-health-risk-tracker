"""
Endpoints for submitting and retrieving raw health indicators per community
per reporting period. Submitting a new indicator set automatically triggers
recomputation of that period's risk score (see risk.py for the read side).
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app import models, schemas
from app.risk_engine import Indicators, compute_risk

router = APIRouter(prefix="/api/communities/{community_id}/indicators", tags=["indicators"])


def _get_community_or_404(db: Session, community_id: int) -> models.Community:
    community = db.query(models.Community).get(community_id)
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")
    return community


@router.post("", response_model=schemas.HealthIndicatorOut, status_code=201)
def submit_indicators(
    community_id: int,
    payload: schemas.HealthIndicatorCreate,
    db: Session = Depends(get_db),
):
    _get_community_or_404(db, community_id)

    record = models.HealthIndicator(community_id=community_id, **payload.model_dump())
    db.add(record)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Indicators for period '{payload.reporting_period}' already submitted "
            "for this community. Use a different period or delete the existing entry.",
        )
    db.refresh(record)

    # Recompute and persist the risk score for this period immediately.
    _recompute_and_store_score(db, community_id, record)

    return record


def _recompute_and_store_score(
    db: Session, community_id: int, record: models.HealthIndicator
) -> models.RiskScore:
    result = compute_risk(
        Indicators(
            diabetes_prevalence_pct=record.diabetes_prevalence_pct,
            hypertension_prevalence_pct=record.hypertension_prevalence_pct,
            obesity_prevalence_pct=record.obesity_prevalence_pct,
            poverty_rate_pct=record.poverty_rate_pct,
            uninsured_rate_pct=record.uninsured_rate_pct,
            food_desert_index=record.food_desert_index,
            providers_per_10k=record.providers_per_10k,
            avg_distance_to_care_miles=record.avg_distance_to_care_miles,
            air_quality_index=record.air_quality_index,
        )
    )

    existing = (
        db.query(models.RiskScore)
        .filter_by(community_id=community_id, reporting_period=record.reporting_period)
        .first()
    )
    if existing:
        existing.composite_score = result.composite_score
        existing.risk_tier = result.risk_tier
        existing.chronic_disease_subscore = result.chronic_disease_subscore
        existing.social_determinants_subscore = result.social_determinants_subscore
        existing.access_subscore = result.access_subscore
        existing.environmental_subscore = result.environmental_subscore
        score_row = existing
    else:
        score_row = models.RiskScore(
            community_id=community_id,
            reporting_period=record.reporting_period,
            composite_score=result.composite_score,
            risk_tier=result.risk_tier,
            chronic_disease_subscore=result.chronic_disease_subscore,
            social_determinants_subscore=result.social_determinants_subscore,
            access_subscore=result.access_subscore,
            environmental_subscore=result.environmental_subscore,
        )
        db.add(score_row)

    db.commit()
    db.refresh(score_row)
    return score_row


@router.get("", response_model=List[schemas.HealthIndicatorOut])
def list_indicators(community_id: int, db: Session = Depends(get_db)):
    _get_community_or_404(db, community_id)
    return (
        db.query(models.HealthIndicator)
        .filter_by(community_id=community_id)
        .order_by(models.HealthIndicator.reporting_period)
        .all()
    )
