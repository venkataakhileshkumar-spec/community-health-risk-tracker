"""
Integration tests for the FastAPI endpoints, using an isolated in-memory
SQLite database (separate from any dev database file on disk).
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


SAMPLE_COMMUNITY = {
    "name": "Test Town",
    "state": "oh",
    "county": "Test County",
    "population": 10000,
}

SAMPLE_INDICATORS = {
    "reporting_period": "2026-06",
    "diabetes_prevalence_pct": 10.0,
    "hypertension_prevalence_pct": 30.0,
    "obesity_prevalence_pct": 28.0,
    "poverty_rate_pct": 15.0,
    "uninsured_rate_pct": 10.0,
    "food_desert_index": 40.0,
    "providers_per_10k": 12.0,
    "avg_distance_to_care_miles": 12.0,
    "air_quality_index": 60.0,
}


def test_health_check(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_create_community(client):
    res = client.post("/api/communities", json=SAMPLE_COMMUNITY)
    assert res.status_code == 201
    body = res.json()
    assert body["name"] == "Test Town"
    assert body["state"] == "OH"  # normalized uppercase
    assert "id" in body


def test_create_duplicate_community_returns_409(client):
    client.post("/api/communities", json=SAMPLE_COMMUNITY)
    res = client.post("/api/communities", json=SAMPLE_COMMUNITY)
    assert res.status_code == 409


def test_create_community_invalid_population_rejected(client):
    bad = dict(SAMPLE_COMMUNITY, population=-5)
    res = client.post("/api/communities", json=bad)
    assert res.status_code == 422


def test_list_communities_filters_by_state(client):
    client.post("/api/communities", json=SAMPLE_COMMUNITY)
    client.post("/api/communities", json=dict(SAMPLE_COMMUNITY, name="Other City", state="ny"))

    res = client.get("/api/communities", params={"state": "oh"})
    assert res.status_code == 200
    names = [c["name"] for c in res.json()]
    assert names == ["Test Town"]


def test_get_community_404(client):
    res = client.get("/api/communities/999")
    assert res.status_code == 404


def test_submit_indicators_and_get_risk_score(client):
    community = client.post("/api/communities", json=SAMPLE_COMMUNITY).json()
    community_id = community["id"]

    res = client.post(f"/api/communities/{community_id}/indicators", json=SAMPLE_INDICATORS)
    assert res.status_code == 201

    score_res = client.get(f"/api/risk/communities/{community_id}/latest")
    assert score_res.status_code == 200
    score = score_res.json()
    assert 0 <= score["composite_score"] <= 100
    assert score["risk_tier"] in {"Low", "Moderate", "High", "Critical"}
    assert score["community_name"] == "Test Town"


def test_submit_indicators_invalid_period_rejected(client):
    community = client.post("/api/communities", json=SAMPLE_COMMUNITY).json()
    bad = dict(SAMPLE_INDICATORS, reporting_period="2026-13")
    res = client.post(f"/api/communities/{community['id']}/indicators", json=bad)
    assert res.status_code == 422


def test_submit_duplicate_period_returns_409(client):
    community = client.post("/api/communities", json=SAMPLE_COMMUNITY).json()
    community_id = community["id"]
    client.post(f"/api/communities/{community_id}/indicators", json=SAMPLE_INDICATORS)
    res = client.post(f"/api/communities/{community_id}/indicators", json=SAMPLE_INDICATORS)
    assert res.status_code == 409


def test_leaderboard_sorted_by_score_descending(client):
    low_risk = dict(SAMPLE_COMMUNITY, name="Healthy Town")
    high_risk = dict(SAMPLE_COMMUNITY, name="At Risk Town")

    low_id = client.post("/api/communities", json=low_risk).json()["id"]
    high_id = client.post("/api/communities", json=high_risk).json()["id"]

    client.post(
        f"/api/communities/{low_id}/indicators",
        json=dict(
            SAMPLE_INDICATORS,
            diabetes_prevalence_pct=4.0,
            hypertension_prevalence_pct=20.0,
            obesity_prevalence_pct=15.0,
            poverty_rate_pct=5.0,
            uninsured_rate_pct=2.0,
            food_desert_index=0.0,
            providers_per_10k=30.0,
            avg_distance_to_care_miles=2.0,
            air_quality_index=25.0,
        ),
    )
    client.post(
        f"/api/communities/{high_id}/indicators",
        json=dict(
            SAMPLE_INDICATORS,
            diabetes_prevalence_pct=16.0,
            hypertension_prevalence_pct=50.0,
            obesity_prevalence_pct=45.0,
            poverty_rate_pct=35.0,
            uninsured_rate_pct=25.0,
            food_desert_index=100.0,
            providers_per_10k=5.0,
            avg_distance_to_care_miles=40.0,
            air_quality_index=200.0,
        ),
    )

    res = client.get("/api/risk/leaderboard")
    assert res.status_code == 200
    body = res.json()
    assert body[0]["community_name"] == "At Risk Town"
    assert body[-1]["community_name"] == "Healthy Town"


def test_risk_history_empty_for_new_community(client):
    community = client.post("/api/communities", json=SAMPLE_COMMUNITY).json()
    res = client.get(f"/api/risk/communities/{community['id']}")
    assert res.status_code == 200
    assert res.json() == []


def test_delete_community(client):
    community = client.post("/api/communities", json=SAMPLE_COMMUNITY).json()
    res = client.delete(f"/api/communities/{community['id']}")
    assert res.status_code == 204
    res2 = client.get(f"/api/communities/{community['id']}")
    assert res2.status_code == 404
