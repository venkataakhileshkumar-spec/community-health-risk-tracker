"""
Pydantic schemas for request validation and response serialization.
"""
import re
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator

PERIOD_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


# ---------- Community ----------

class CommunityBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    state: str = Field(..., min_length=2, max_length=2)
    county: Optional[str] = Field(None, max_length=120)
    population: int = Field(..., gt=0)

    @field_validator("state")
    @classmethod
    def uppercase_state(cls, v: str) -> str:
        return v.upper()


class CommunityCreate(CommunityBase):
    pass


class CommunityOut(CommunityBase):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------- Health Indicators ----------

class HealthIndicatorBase(BaseModel):
    reporting_period: str = Field(..., description="Format YYYY-MM, e.g. 2026-06")

    diabetes_prevalence_pct: float = Field(..., ge=0, le=100)
    hypertension_prevalence_pct: float = Field(..., ge=0, le=100)
    obesity_prevalence_pct: float = Field(..., ge=0, le=100)

    poverty_rate_pct: float = Field(..., ge=0, le=100)
    uninsured_rate_pct: float = Field(..., ge=0, le=100)
    food_desert_index: float = Field(..., ge=0, le=100)

    providers_per_10k: float = Field(..., ge=0)
    avg_distance_to_care_miles: float = Field(..., ge=0)

    air_quality_index: float = Field(..., ge=0, le=500)

    @field_validator("reporting_period")
    @classmethod
    def validate_period(cls, v: str) -> str:
        if not PERIOD_PATTERN.match(v):
            raise ValueError("reporting_period must match YYYY-MM")
        return v


class HealthIndicatorCreate(HealthIndicatorBase):
    pass


class HealthIndicatorOut(HealthIndicatorBase):
    id: int
    community_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------- Risk Score ----------

class RiskScoreOut(BaseModel):
    id: int
    community_id: int
    reporting_period: str
    composite_score: float
    risk_tier: str
    chronic_disease_subscore: float
    social_determinants_subscore: float
    access_subscore: float
    environmental_subscore: float
    created_at: datetime

    model_config = {"from_attributes": True}


class RiskScoreDetail(RiskScoreOut):
    community_name: str
    contributing_factors: List[str] = []


class CommunityRiskSummary(BaseModel):
    community_id: int
    community_name: str
    state: str
    latest_period: Optional[str]
    latest_score: Optional[float]
    latest_tier: Optional[str]
    trend: Optional[str] = Field(
        None, description="'worsening', 'improving', 'stable', or None if insufficient history"
    )
