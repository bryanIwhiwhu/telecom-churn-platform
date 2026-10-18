"""Feature definitions shared by training and serving, so they can never drift apart."""

from __future__ import annotations

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

NUMERIC = ["tenure_months", "monthly_charges", "total_charges", "senior_citizen",
           "has_partner", "has_dependents", "paperless_billing"]
CATEGORICAL = ["gender", "phone_service", "multiple_lines", "internet_service",
               "online_security", "online_backup", "device_protection", "tech_support",
               "streaming_tv", "streaming_movies", "contract_type", "payment_method"]
FEATURES = NUMERIC + CATEGORICAL
TARGET = "churned"


def load_training_frame(engine: Engine) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(text("SELECT * FROM customer_features"), conn)


def load_customer(engine: Engine, customer_id: str) -> pd.DataFrame:
    cols = ", ".join(["customer_id", *FEATURES])
    with engine.connect() as conn:
        return pd.read_sql(
            text(f"SELECT {cols} FROM customer_features WHERE customer_id = :cid"),
            conn, params={"cid": customer_id},
        )
