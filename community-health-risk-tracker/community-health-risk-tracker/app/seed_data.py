"""
Seeds the database with a handful of sample communities and two reporting
periods of indicator data so the API and dashboard have something to show
out of the box. Safe to re-run (skips communities that already exist).

Usage:
    python -m app.seed_data
"""
from app.database import SessionLocal, Base, engine
from app import models
from app.routers.indicators import _recompute_and_store_score

Base.metadata.create_all(bind=engine)

SAMPLE_COMMUNITIES = [
    {"name": "Riverdale", "state": "OH", "county": "Franklin", "population": 42000},
    {"name": "Maple Heights", "state": "OH", "county": "Cuyahoga", "population": 18500},
    {"name": "Sunridge", "state": "AZ", "county": "Maricopa", "population": 61000},
    {"name": "Pinecrest Valley", "state": "NC", "county": "Wake", "population": 27500},
]

# (community_name, period) -> indicator dict
SAMPLE_INDICATORS = {
    ("Riverdale", "2026-05"): dict(
        diabetes_prevalence_pct=11.2, hypertension_prevalence_pct=34.0, obesity_prevalence_pct=32.0,
        poverty_rate_pct=18.5, uninsured_rate_pct=12.0, food_desert_index=55.0,
        providers_per_10k=9.0, avg_distance_to_care_miles=14.0, air_quality_index=62.0,
    ),
    ("Riverdale", "2026-06"): dict(
        diabetes_prevalence_pct=11.8, hypertension_prevalence_pct=35.5, obesity_prevalence_pct=33.0,
        poverty_rate_pct=19.2, uninsured_rate_pct=13.0, food_desert_index=58.0,
        providers_per_10k=8.5, avg_distance_to_care_miles=15.0, air_quality_index=68.0,
    ),
    ("Maple Heights", "2026-06"): dict(
        diabetes_prevalence_pct=7.5, hypertension_prevalence_pct=26.0, obesity_prevalence_pct=24.0,
        poverty_rate_pct=9.0, uninsured_rate_pct=5.0, food_desert_index=20.0,
        providers_per_10k=18.0, avg_distance_to_care_miles=4.5, air_quality_index=40.0,
    ),
    ("Sunridge", "2026-06"): dict(
        diabetes_prevalence_pct=14.5, hypertension_prevalence_pct=41.0, obesity_prevalence_pct=38.0,
        poverty_rate_pct=27.0, uninsured_rate_pct=19.0, food_desert_index=72.0,
        providers_per_10k=6.0, avg_distance_to_care_miles=22.0, air_quality_index=95.0,
    ),
    ("Pinecrest Valley", "2026-06"): dict(
        diabetes_prevalence_pct=5.5, hypertension_prevalence_pct=22.0, obesity_prevalence_pct=19.0,
        poverty_rate_pct=6.0, uninsured_rate_pct=3.5, food_desert_index=10.0,
        providers_per_10k=24.0, avg_distance_to_care_miles=3.0, air_quality_index=30.0,
    ),
}


def run():
    db = SessionLocal()
    try:
        name_to_id = {}
        for c in SAMPLE_COMMUNITIES:
            existing = (
                db.query(models.Community)
                .filter_by(name=c["name"], state=c["state"])
                .first()
            )
            if existing:
                name_to_id[c["name"]] = existing.id
                continue
            community = models.Community(**c)
            db.add(community)
            db.commit()
            db.refresh(community)
            name_to_id[c["name"]] = community.id
            print(f"Created community: {c['name']}, {c['state']}")

        for (name, period), values in SAMPLE_INDICATORS.items():
            community_id = name_to_id[name]
            existing = (
                db.query(models.HealthIndicator)
                .filter_by(community_id=community_id, reporting_period=period)
                .first()
            )
            if existing:
                continue
            record = models.HealthIndicator(
                community_id=community_id, reporting_period=period, **values
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            _recompute_and_store_score(db, community_id, record)
            print(f"Seeded indicators + risk score for {name} ({period})")

        print("Seed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
