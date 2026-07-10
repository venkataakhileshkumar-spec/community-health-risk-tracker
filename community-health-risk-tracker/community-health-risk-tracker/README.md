# Community Health Risk Tracker

A population-health monitoring service that tracks community-level health
indicators and computes a transparent, weighted **composite risk score**
(0–100) to help prioritize outreach, funding, and program design.

Built with **FastAPI + SQLAlchemy**, a rules-based **risk scoring engine**,
and a lightweight built-in dashboard (no frontend build step required).

---

## Why a rules-based score instead of ML?

For resource-allocation decisions that affect real communities, stakeholders
need to see *exactly* why a place was flagged high-risk. The engine in
`app/risk_engine.py` is a fully transparent weighted model — every input,
normalization bound, and weight is documented and easy to audit or tune as
better reference data (CDC PLACES, ACS estimates, EPA thresholds) becomes
available.

## Risk model

| Subscore | Weight | Inputs |
|---|---|---|
| Chronic Disease Burden | 35% | diabetes, hypertension, obesity prevalence |
| Social Determinants of Health | 30% | poverty rate, uninsured rate, food desert index |
| Healthcare Access | 25% | providers per 10k residents, avg. distance to care |
| Environmental Exposure | 10% | air quality index (EPA AQI scale) |

Composite score maps to a risk tier:

| Score | Tier |
|---|---|
| 0–24.9 | Low |
| 25–49.9 | Moderate |
| 50–74.9 | High |
| 75–100 | Critical |

## Project structure

```
community-health-risk-tracker/
├── app/
│   ├── main.py              # FastAPI app + router wiring
│   ├── database.py          # SQLAlchemy engine/session
│   ├── models.py            # ORM models (Community, HealthIndicator, RiskScore)
│   ├── schemas.py            # Pydantic request/response models
│   ├── risk_engine.py       # Composite risk scoring logic
│   ├── seed_data.py         # Sample data loader
│   └── routers/
│       ├── communities.py   # Community CRUD
│       ├── indicators.py    # Indicator submission (triggers scoring)
│       └── risk.py          # Risk history, latest score, leaderboard
├── frontend/
│   └── index.html           # Dashboard (vanilla JS + Chart.js via CDN)
├── tests/
│   ├── test_risk_engine.py  # Unit tests for scoring math
│   └── test_api.py          # API integration tests (in-memory DB)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## Quick start (local)

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt

# optional: load sample communities + indicators
python -m app.seed_data

uvicorn app.main:app --reload
```

Open **http://localhost:8000** for the dashboard, or
**http://localhost:8000/docs** for interactive API docs (Swagger UI).

## Quick start (Docker)

```bash
docker compose up --build
```

Data persists in a named Docker volume (`health_data`) so it survives
container restarts.

## Running tests

```bash
pytest -v
```

## API overview

| Method | Path | Description |
|---|---|---|
| POST | `/api/communities` | Create a community |
| GET | `/api/communities` | List communities (optional `?state=OH`) |
| GET | `/api/communities/{id}` | Get one community |
| DELETE | `/api/communities/{id}` | Delete a community |
| POST | `/api/communities/{id}/indicators` | Submit indicators for a reporting period (auto-scores) |
| GET | `/api/communities/{id}/indicators` | List submitted indicator periods |
| GET | `/api/risk/communities/{id}` | Full risk score history for a community |
| GET | `/api/risk/communities/{id}/latest` | Latest score + top contributing factors |
| GET | `/api/risk/leaderboard` | All communities ranked by current risk, with trend |
| GET | `/api/health` | Liveness check |

### Example: submit indicators

```bash
curl -X POST http://localhost:8000/api/communities/1/indicators \
  -H "Content-Type: application/json" \
  -d '{
    "reporting_period": "2026-06",
    "diabetes_prevalence_pct": 11.8,
    "hypertension_prevalence_pct": 35.5,
    "obesity_prevalence_pct": 33.0,
    "poverty_rate_pct": 19.2,
    "uninsured_rate_pct": 13.0,
    "food_desert_index": 58.0,
    "providers_per_10k": 8.5,
    "avg_distance_to_care_miles": 15.0,
    "air_quality_index": 68.0
  }'
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./community_health.db` | Any SQLAlchemy-compatible DSN (swap in Postgres/MySQL for production) |

## Notes on extending this project

- **Swap the database**: change `DATABASE_URL` to a Postgres/MySQL DSN — no code changes needed.
- **Tune the model**: adjust `BOUNDS` and `WEIGHT_*` constants in `risk_engine.py` as better local benchmarks become available.
- **Add auth**: none is included by default; put this behind an API gateway or add OAuth2/JWT middleware before exposing publicly, especially since this stores identifiable community-level health data.
- **Historical trend charts**: `GET /api/risk/communities/{id}` already returns full history — wire it into a line chart on the dashboard.
