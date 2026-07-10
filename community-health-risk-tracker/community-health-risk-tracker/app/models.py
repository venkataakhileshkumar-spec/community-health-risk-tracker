"""
ORM models for communities, their health indicators, and computed risk scores.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class Community(Base):
    __tablename__ = "communities"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False, index=True)
    state = Column(String(2), nullable=False)
    county = Column(String(120), nullable=True)
    population = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    indicators = relationship(
        "HealthIndicator", back_populates="community", cascade="all, delete-orphan"
    )
    risk_scores = relationship(
        "RiskScore", back_populates="community", cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("name", "state", name="uq_community_name_state"),)


class HealthIndicator(Base):
    """
    Raw indicator values reported for a community for a given reporting period.
    Values are stored as rates/percentages/indices on a 0-100-ish scale where
    applicable; the risk engine documents exact expected ranges per indicator.
    """
    __tablename__ = "health_indicators"

    id = Column(Integer, primary_key=True, index=True)
    community_id = Column(Integer, ForeignKey("communities.id"), nullable=False)
    reporting_period = Column(String(7), nullable=False)  # e.g. "2026-06"

    # Chronic disease burden
    diabetes_prevalence_pct = Column(Float, nullable=False, default=0.0)
    hypertension_prevalence_pct = Column(Float, nullable=False, default=0.0)
    obesity_prevalence_pct = Column(Float, nullable=False, default=0.0)

    # Social determinants of health
    poverty_rate_pct = Column(Float, nullable=False, default=0.0)
    uninsured_rate_pct = Column(Float, nullable=False, default=0.0)
    food_desert_index = Column(Float, nullable=False, default=0.0)  # 0 (no access issue) - 100 (severe)

    # Healthcare access
    providers_per_10k = Column(Float, nullable=False, default=0.0)
    avg_distance_to_care_miles = Column(Float, nullable=False, default=0.0)

    # Environmental / other
    air_quality_index = Column(Float, nullable=False, default=0.0)  # EPA AQI scale

    created_at = Column(DateTime, default=datetime.utcnow)

    community = relationship("Community", back_populates="indicators")

    __table_args__ = (
        UniqueConstraint("community_id", "reporting_period", name="uq_indicator_period"),
    )


class RiskScore(Base):
    """
    Computed composite risk score for a community/reporting period, produced
    by the risk engine. Stored so history can be queried without recomputation.
    """
    __tablename__ = "risk_scores"

    id = Column(Integer, primary_key=True, index=True)
    community_id = Column(Integer, ForeignKey("communities.id"), nullable=False)
    reporting_period = Column(String(7), nullable=False)

    composite_score = Column(Float, nullable=False)  # 0-100
    risk_tier = Column(String(20), nullable=False)  # Low / Moderate / High / Critical

    chronic_disease_subscore = Column(Float, nullable=False)
    social_determinants_subscore = Column(Float, nullable=False)
    access_subscore = Column(Float, nullable=False)
    environmental_subscore = Column(Float, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    community = relationship("Community", back_populates="risk_scores")

    __table_args__ = (
        UniqueConstraint("community_id", "reporting_period", name="uq_score_period"),
    )
