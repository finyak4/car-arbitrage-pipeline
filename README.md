# 🚗 Toyota Car Arbitrage — End-to-End MLOps Pipeline

> **Scrape Toyota listings from the Polish market. Train a price prediction model. Deploy it in a daily Airflow pipeline that surfaces arbitrage deals from foreign markets.**

---

## Business Context

A trading company buys used Toyota vehicles from **foreign European car markets** and resells them on the **Polish market** at a profit. The core challenge: identify which foreign listings, at their current asking price, will generate a meaningful margin once imported and sold domestically.

This system automates the full decision pipeline:

1. **Daily at 08:00 UTC** — an Airflow DAG fetches fresh foreign listings (mocked; real scraper is the next milestone)
2. **Inference** — listings are scored by an XGBoost model trained on ~20,000 real Polish Toyota listings
3. **Filtering** — only cars where `(predicted_PLN − listed_price) / listed_price > 15%` are surfaced
4. **Review** — analysts open the Streamlit dashboard, browse the flagged deals, and click through to the original listing URL to make the final call

The model does the heavy lifting of price estimation at scale. Humans make the final purchase decision.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Apache Airflow                             │
│                                                                 │
│   car_arbitrage_deal_scorer  (runs daily @ 08:00 UTC)           │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │             process_and_score_deals                     │   │
│   │                                                         │   │
│   │  1. Read mock_data.csv  (→ real scraper: future work)  │   │
│   │  2. Load model from MLflow Registry                    │   │
│   │  3. Predict Polish market price for each car           │   │
│   │  4. Filter deals with >15% predicted margin            │   │
│   │  5. Upsert to data/selected_deals.db (url = PK)        │   │
│   └─────────────────────────────────────────────────────────┘   │
└───────────────────────────┬─────────────────────────────────────┘
                            │ mlflow.pyfunc.load_model()
         ┌──────────────────▼──────────────────────────┐
         │                MLflow Server                 │
         │  Experiment: car-price                       │
         │  Registry:   car-price-xgb_v0.1 (v2)        │
         │  Backend:    sqlite:///mlflow.db             │
         │  Artifacts:  ./mlartifacts/                  │
         └──────────────────────────────────────────────┘

         ┌──────────────────────────────────────────────┐
         │           Streamlit Dashboard                │
         │  • Summary metrics (deal count, avg margin)  │
         │  • Filterable deal cards (model, fuel, body) │
         │  • Direct "Visit listing" links              │
         └──────────────────────────────────────────────┘
```

### Docker Compose Services

| Service | Image | Role |
|---|---|---|
| `airflow-apiserver` | custom Airflow | Web UI + REST API (port 8080) |
| `airflow-scheduler` | custom Airflow | DAG scheduling |
| `airflow-dag-processor` | custom Airflow | DAG file parsing |
| `airflow-worker` | custom Airflow | Celery task executor — runs the pipeline |
| `airflow-triggerer` | custom Airflow | Deferred / sensor task support |
| `mlflow-server` | python:3.11-slim | MLflow tracking server + artifact proxy (port 5000) |
| `postgres` | postgres:16 | Airflow metadata database |
| `redis` | redis:7.2 | Celery message broker |
| `streamlit-app` | custom | Analyst-facing deal dashboard (port 8501) |

---

## The ML Model

Training data: **~20,000 Polish Toyota listings** scraped from otomoto.pl.

### Feature Engineering

The sklearn pipeline handles heterogeneous feature types:

| Feature group | Columns | Encoding |
|---|---|---|
| Numeric — median imputed | `engine_power`, `engine_capacity`, `nr_seats`, `door_count` | `StandardScaler` |
| Numeric — zero imputed | `mileage`, `number_engines`, hybrid power fields | `StandardScaler` |
| Categorical — standard | `transmission`, `gearbox`, `body_type`, `fuel_type` | `OneHotEncoder` |
| Categorical — high cardinality | `model_trim` | `TargetEncoder` (smooth auto) |
| Categorical — rare classes | `color`, `new_used`, `seller_type`, `has_registration` | `OneHotEncoder` (infrequent grouping) |
| Multi-label list | `equipment` (JSON list per car) | Custom `EquipmentEncoder` |

**`EquipmentEncoder`** is a custom `sklearn` transformer: it binarises the equipment list per car, then drops any feature present in fewer than 1% of listings — preventing noise from rare options like heated rear seats in a specific trim.

### Model

```
TransformedTargetRegressor(
    regressor = Pipeline([
        ColumnTransformer(preprocessor),
        XGBRegressor(
            n_estimators=500, learning_rate=0.05,
            max_depth=6,     subsample=0.8,
            reg_alpha=2.0,   reg_lambda=5.0
        )
    ]),
    func=np.log1p,          # train on log(price+1) → reduces skew
    inverse_func=np.expm1   # predictions are exp-transformed back
)
```

The log-transform on the target stabilises variance across the wide PLN price range (30k–300k+).

---

## Project Structure

```
.
├── dags/
│   └── mock_deals_dag.py           # Airflow DAG — daily scoring pipeline
│
├── src/
│   ├── cli.py                      # Typer CLI entry point
│   ├── config.py                   # Pydantic settings (env vars)
│   ├── database.py                 # SQLite helpers (URL store)
│   │
│   ├── scraper/
│   │   ├── phase1_urls.py          # Playwright stealth scraper — URL discovery
│   │   └── phase2_data.py          # Playwright scraper — full listing details
│   │
│   ├── data/
│   │   └── clean.py                # Data cleaning pipeline (raw → clean DB)
│   │
│   ├── model/
│   │   ├── preprocessing.py        # Custom sklearn transformer (EquipmentEncoder)
│   │   ├── train.py                # Full training pipeline + MLflow logging
│   │   └── predict.py              # Inference + deal filtering + SQLite upsert
│   │
│   └── utils/
│       └── logger.py               # Structured logging setup
│
├── data/                           # Runtime data (committed — no copyright)
│   ├── cars_data_pipeline_complete.db  # Raw scraped listings
│   ├── cars_data_clean_new.db          # Cleaned training data (~20k rows)
│   ├── mock_data.csv                   # Mock foreign market listings for the DAG
│   └── selected_deals.db               # Output — deals flagged by the pipeline
│
├── mlartifacts/                    # MLflow artifact store (model binaries)
├── app.py                          # Streamlit dashboard (420 lines, custom CSS)
├── Dockerfile.airflow              # Custom Airflow image with ML dependencies
├── docker-compose.yaml             # Full 9-service stack
├── pyproject.toml                  # Hatchling build + all dependencies
└── Makefile                        # Developer convenience commands
```

---

## Getting Started

### Prerequisites

- Docker Desktop (4 GB RAM allocated minimum)
- Python ≥ 3.12 (for local training only)
- `make` (optional)

### 1. Clone and configure

```bash
git clone https://github.com/finyak4/car-arbitrage-pipeline.git
cd car-arbitrage-pipeline
cp .env.example .env
```

Edit `.env` — at minimum generate a Fernet key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# paste the output as FERNET_KEY in .env
```

### 2. Start all services

```bash
docker compose up -d --build
```

First boot takes 2–3 minutes (Airflow init, MLflow pip install). Services are ready when:

```bash
docker compose ps   # all show "healthy" or "running"
```

### 3. Open the UIs

| Service | URL | Credentials |
|---|---|---|
| Airflow | http://localhost:8080 | `airflow` / `airflow` |
| MLflow | http://localhost:5000 | — |
| Streamlit | http://localhost:8501 | — |

### 4. Train the model (first time only)

The model must be registered in MLflow before the DAG can run. Training uses the cleaned Polish market data in `data/cars_data_clean_new.db`.

```bash
pip install -e ".[dev]"
python -m src.model.train
```

This logs hyperparameters, fits the pipeline on ~20,000 rows, and registers the model as `car-price-xgb_v0.1` in MLflow.

### 5. Run the pipeline

In the Airflow UI at http://localhost:8080:
1. Unpause `car_arbitrage_deal_scorer`
2. Click **Trigger DAG**
3. Wait ~10 seconds for the task to complete
4. Open http://localhost:8501 — flagged deals appear in the dashboard

---

## Development

```bash
pip install -e ".[dev]"
playwright install chromium

make format         # ruff format + ruff check --fix
make lint           # ruff check + mypy + bandit

# Scraping pipeline (Polish market data collection)
make setup          # initialise SQLite database
make discover       # phase 1 — collect listing URLs (APP_DISCOVERY_PAGES pages)
make retrieve_data  # phase 2 — scrape full details (APP_RETRIEVE_PAGES listings)
make clean          # clean raw → cleaned DB
```

---

## Roadmap

### Infrastructure
- [ ] Replace the MLflow container's `pip install` startup command with a purpose-built Docker image
- [ ] Migrate DAG imports from deprecated `airflow.decorators` → `airflow.sdk`
- [ ] Package `src/` properly inside the Airflow image to remove the `sys.path` workaround in the DAG

### Data & Modelling
- [ ] Connect the DAG to a real foreign market scraper instead of mock CSV data
- [ ] Add model drift detection — monitor the prediction distribution over time
- [ ] Explore a Vision model to assess car condition from listing photos (replaces paid condition APIs)

---

## License

MIT — data is sourced from public listings and used for educational purposes.
