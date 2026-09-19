import json
import os
import sqlite3
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import (
    OneHotEncoder,
    StandardScaler,
    TargetEncoder,
)

from src.model.preprocessing import EquipmentEncoder
from src.utils.logger import get_logger

logger = get_logger("train")

mlflow.set_tracking_uri("http://localhost:5000")
mlflow.set_experiment("car-price")

DATA_DIR = Path(os.getenv("APP_DIR", "."), "data")

conn = sqlite3.connect(DATA_DIR / "cars_data_clean_new.db")
cursor = conn.cursor()
rows = cursor.execute("SELECT * FROM cars_cleaned").fetchall()
df = pd.DataFrame(rows, columns=[col[0] for col in cursor.description])
df["equipment"] = df["equipment"].apply(json.loads)
df = df.dropna(subset=["mileage"])
df.head()
X = df.drop("price", axis=1)
y = df.price


features_median = ["engine_power", "engine_capacity", "nr_seats", "door_count"]
features_zero = [
    "mileage",
    "number_engines",
    "system_performance_of_hybrid_driveline_in_hp",
    "electric_power_peak",
]

median_pipeline = Pipeline(
    steps=[("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]
)

zero_pipeline = Pipeline(
    steps=[
        ("imputer", SimpleImputer(strategy="constant", fill_value=0)),
        ("scaler", StandardScaler()),
    ]
)

ohe = OneHotEncoder(handle_unknown="ignore", min_frequency=0.05)
ohe_color = OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=0.05)

new_used_pipe = Pipeline(
    [
        ("imputer", SimpleImputer(strategy="constant", fill_value="Używany")),
        ("ohe", ohe),
    ]
)

seller_type_pipe = Pipeline(
    [
        ("imputer", SimpleImputer(strategy="constant", fill_value="Osoba prywatna")),
        ("ohe", ohe),
    ]
)

has_registration_pipe = Pipeline(
    [("imputer", SimpleImputer(strategy="constant", fill_value="Nie")), ("ohe", ohe)]
)

standard_cat_features = ["transmission", "gearbox", "body_type", "fuel_type"]
standard_cat_pipe = Pipeline(
    [("imputer", SimpleImputer(strategy="most_frequent")), ("ohe", ohe)]
)

color_pipe = Pipeline(
    [("imputer", SimpleImputer(strategy="most_frequent")), ("encoder", ohe_color)]
)

model_trim_pipe = Pipeline(
    [
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("target_enc", TargetEncoder(target_type="continuous", smooth="auto")),
    ]
)

equipment_pipe = Pipeline([("encoder", EquipmentEncoder(min_frequency=0.01))])

preprocessor = ColumnTransformer(
    transformers=[
        ("num_median", median_pipeline, features_median),
        ("num_zero", zero_pipeline, features_zero),
        ("cat_new_used", new_used_pipe, ["new_used"]),
        ("cat_seller", seller_type_pipe, ["seller_type"]),
        ("cat_registration", has_registration_pipe, ["has_registration"]),
        ("cat_standard", standard_cat_pipe, standard_cat_features),
        ("cat_color", color_pipe, ["color"]),
        ("target_model_trim", model_trim_pipe, ["model_trim"]),
        ("cat_equipment", equipment_pipe, ["equipment"]),
    ],
    remainder="drop",
)


xgb_pipeline = Pipeline(
    [
        ("preprocessor", preprocessor),
        (
            "model",
            xgb.XGBRegressor(
                n_estimators=500,
                learning_rate=0.05,
                max_depth=6,
                subsample=0.8,
                reg_alpha=2.0,
                reg_lambda=5.0,
                random_state=42,
                n_jobs=-1,
            ),
        ),
    ]
)

final_model = TransformedTargetRegressor(
    # regressor=base_model,
    regressor=xgb_pipeline,
    func=np.log1p,
    inverse_func=np.expm1,
)

xgb_params = xgb_pipeline.named_steps["model"].get_params()

logger.info("Starting MLflow training run — experiment: car-price")
with mlflow.start_run():
    mlflow.log_params(xgb_params)
    logger.info("Fitting final model on %d rows", len(X))
    final_model.fit(X, y)
    logger.info("Model fit complete — logging to MLflow")
    mlflow.sklearn.log_model(
        sk_model=final_model,
        artifact_path="model",
        registered_model_name="car-price-xgb_v0.1",
        skops_trusted_types=[
            "src.model.preprocessing.EquipmentEncoder",
            "numpy.dtype",
            "xgboost.core.Booster",
            "xgboost.sklearn.XGBRegressor",
        ],
        run_id=mlflow.active_run().info.run_id,
    )
    logger.info("MLflow run complete — model registered as car-price-xgb_v0.1")
