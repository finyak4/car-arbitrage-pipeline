# 🚗 Toyota Car Arbitrage — End-to-End MLOps Pipeline

> **Find underpriced Toyotas on foreign European markets. Predict their Polish resale value. Surface only the deals worth buying.**

---

## Business Context

A trading company purchases used Toyota vehicles from foreign European car markets (e.g. Germany, Belgium, Netherlands) and resells them on the Polish market at a profit. The challenge is identifying which cars, at their listed foreign price, will yield a meaningful margin once imported and sold domestically.

This system automates that decision process end-to-end:

1. **Every day at 08:00 UTC**, an Airflow DAG fetches fresh listings from a foreign car market (currently mocked; see [roadmap](#roadmap))
2. The listings are passed through a **price prediction model** trained on Polish market data
3. Any car where `(predicted_PLN_price − foreign_asking_price) / foreign_asking_price > 15%` is flagged as a deal
4. A **Streamlit dashboard** surfaces those deals to the company's analysts, who review each URL and make the final purchase decision

The ML model does the heavy lifting of price estimation at scale; the humans make the final call.

---

## Architecture

```
                     ┌─────────────────────────────────────────┐
                     │            Apache Airflow                │
                     │                                          │
                     │  car_arbitrage_deal_scorer (DAG)         │
                     │  ┌─────────────────────────────────┐    │
                     │  │  process_and_score_deals (task) │    │
                     │  │                                 │    │
                     │  │  1. Load mock foreign listings  │    │
                     │  │  2. Call MLflow model           │    │
                     │  │  3. Filter >15% margin deals    │    │
                     │  │  4. Save to SQLite              │    │
                     │  └─────────────────────────────────┘    │
                     └─────────────┬───────────────────────────┘
                                   │
              ┌────────────────────▼──────────────────────┐
              │              MLflow Server                 │
              │  • Model Registry (car-price-xgb_v0.1)    │
              │  • XGBoost model trained on Polish market  │
              │  • Artifact storage + experiment tracking  │
              └────────────────────┬──────────────────────┘
                                   │
              ┌────────────────────▼──────────────────────┐
              │           Streamlit Dashboard              │
              │  • Lists flagged deals with predicted PLN  │
              │  • Clickable URLs for analyst review       │
              └───────────────────────────────────────────┘
```

### Services (Docker Compose)

| Service | Role |
|---|---|
| `airflow-apiserver` | Airflow web UI & REST API |
| `airflow-scheduler` | DAG scheduling |
| `airflow-dag-processor` | DAG file parsing |
| `airflow-worker` | Celery task execution (runs the scoring pipeline) |
| `airflow-triggerer` | Deferred task support |
| `mlflow-server` | MLflow tracking server & model registry |
| `postgres` | Airflow metadata database |
| `redis` | Celery message broker |
| `streamlit-app` | Analyst-facing deal dashboard |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Orchestration | Apache Airflow 3.3 (CeleryExecutor) |
| ML Model | XGBoost (trained with scikit-learn pipeline) |
| Model Registry | MLflow |
| Dashboard | Streamlit |
| Scraping | Playwright + playwright-stealth |
| Data | pandas, SQLite |
| Containerisation | Docker Compose |
| Code Quality | Ruff, mypy, Bandit, pre-commit |
| Dependency Mgmt | Hatchling (`pyproject.toml`) |

---

## Project Structure

```
.
├── dags/
│   └── mock_deals_dag.py        # Airflow DAG — daily scoring pipeline
├── src/
│   ├── cli.py                   # Typer CLI (init_db, discover, retrieve_data, clean)
│   ├── config.py                # Pydantic settings
│   ├── database.py              # SQLite helpers
│   ├── model/
│   │   ├── train.py             # Model training + MLflow logging
│   │   └── predict.py           # Inference + deal filtering + DB persistence
│   ├── scraper/
│   │   └── phase2_data.py       # Playwright-based foreign market scraper
│   ├── data/                    # Mock CSVs and SQLite deal store
│   └── utils/
├── data/                        # Runtime data (mock_data.csv, selected_deals.db)
├── mlartifacts/                 # MLflow artifact store
├── mlflow.db                    # MLflow tracking database
├── app.py                       # Streamlit dashboard
├── Dockerfile.airflow           # Custom Airflow image with ML deps
├── docker-compose.yaml
├── pyproject.toml
└── Makefile
```

---

## Getting Started

### Prerequisites

- Docker Desktop
- `make` (optional, for convenience commands)

### 1. Clone and configure

```bash
git clone <repo-url>
cd <repo>
cp .env.example .env   # fill in FERNET_KEY and other vars
```

Generate a Fernet key if you don't have one:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 2. Build and start all services

```bash
docker compose up -d --build
```

First startup takes a few minutes — the Airflow image installs ML dependencies and the MLflow server runs its schema migration.

### 3. Access the UIs

| Interface | URL | Default credentials |
|---|---|---|
| Airflow | http://localhost:8080 | `airflow` / `airflow` |
| MLflow | http://localhost:5000 | — |
| Streamlit | http://localhost:8501 | — |

### 4. Train the model (first time)

The model must be trained and registered in MLflow before the DAG can run:

```bash
# From inside the project, with the venv active:
pip install -e ".[dev]"
python -m src.model.train
```

This logs the XGBoost model to MLflow under the experiment `car-price` and registers it as `car-price-xgb_v0.1`.

### 5. Trigger the pipeline

In the Airflow UI, unpause and manually trigger `car_arbitrage_deal_scorer`. On success, flagged deals appear in the Streamlit dashboard.

---

## Development

```bash
# Install with dev extras
pip install -e ".[dev]"
playwright install chromium

# Format & lint
make format
make lint

# CLI helpers
make setup          # initialise SQLite database
make discover       # run discovery scraper
make retrieve_data  # fetch full listing details
make clean          # clean raw data
```

---

## Roadmap

This project intentionally simplifies certain areas to remain a clean learning artifact. Planned future work:

### Infrastructure & Reliability
- [ ] Replace `pip install` in the MLflow container startup with a proper dedicated Docker image
- [ ] Migrate DAGs from deprecated `airflow.decorators` to `airflow.sdk`
- [ ] Install `src` as a proper package inside the Airflow image (eliminate `sys.path` manipulation)
- [ ] Expand test coverage — unit tests for feature engineering and model I/O, integration tests for the full DAG

### Data & Modelling
- [ ] Replace mock data with a live scraper of the actual foreign market source
- [ ] Add **model drift detection** — monitor prediction distribution over time and alert when the model degrades
- [ ] Improve car condition features — condition/history data from paid APIs is not cost-justified for a learning project today, but would materially improve model accuracy
- [ ] Explore a **Vision model** to automatically assess car condition from listing photos, replacing the need for paid condition data entirely

---

## License

MIT
