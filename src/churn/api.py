"""FastAPI service: churn scoring, monitoring and the analytics agent.

Run locally:  uvicorn churn.api:app --reload
Docs:         http://localhost:8000/docs
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from functools import lru_cache
from typing import Literal

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from churn import config
from churn.etl import get_engine
from churn.features import FEATURES, load_customer
from churn.monitoring import drift_report

app = FastAPI(title="Telecom Churn Platform", version="1.0.0")

YesNoService = Literal["Yes", "No", "No internet service"]


class CustomerFeatures(BaseModel):
    """Features for scoring a customer who is not in the warehouse yet."""

    gender: Literal["Male", "Female"]
    senior_citizen: int = Field(ge=0, le=1)
    has_partner: int = Field(ge=0, le=1)
    has_dependents: int = Field(ge=0, le=1)
    tenure_months: int = Field(ge=0, le=120)
    phone_service: Literal["Yes", "No"]
    multiple_lines: Literal["Yes", "No", "No phone service"]
    internet_service: Literal["DSL", "Fiber optic", "No"]
    online_security: YesNoService
    online_backup: YesNoService
    device_protection: YesNoService
    tech_support: YesNoService
    streaming_tv: YesNoService
    streaming_movies: YesNoService
    contract_type: Literal["Month-to-month", "One year", "Two year"]
    paperless_billing: int = Field(ge=0, le=1)
    payment_method: Literal["Electronic check", "Mailed check",
                            "Bank transfer (automatic)", "Credit card (automatic)"]
    monthly_charges: float = Field(gt=0, le=500)
    total_charges: float = Field(ge=0)


class Prediction(BaseModel):
    customer_id: str | None
    churn_probability: float
    risk_band: Literal["low", "medium", "high"]
    model_version: str


class AgentQuestion(BaseModel):
    question: str = Field(min_length=5, max_length=500)


@lru_cache
def model_bundle() -> dict:
    if not config.MODEL_PATH.exists():
        raise HTTPException(503, "Model not trained yet. Run: python -m churn.train")
    return joblib.load(config.MODEL_PATH)


def risk_band(p: float) -> str:
    return "high" if p >= 0.6 else "medium" if p >= 0.3 else "low"


def score(frame: pd.DataFrame, customer_id: str | None) -> Prediction:
    bundle = model_bundle()
    p = float(bundle["pipeline"].predict_proba(frame[FEATURES])[0, 1])
    row = frame.iloc[0]
    with get_engine().begin() as conn:  # log every prediction for monitoring
        conn.execute(text(
            "INSERT INTO prediction_log (created_at, model_version, customer_id, churn_probability, "
            "tenure_months, monthly_charges, contract_type) "
            "VALUES (:ts, :v, :cid, :p, :t, :m, :c)"),
            {"ts": datetime.now(UTC).isoformat(), "v": bundle["version"], "cid": customer_id,
             "p": round(p, 4), "t": int(row["tenure_months"]), "m": float(row["monthly_charges"]),
             "c": row["contract_type"]})
    return Prediction(customer_id=customer_id, churn_probability=round(p, 4),
                      risk_band=risk_band(p), model_version=bundle["version"])


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model_loaded": config.MODEL_PATH.exists()}


@app.post("/predict", response_model=Prediction)
def predict(features: CustomerFeatures) -> Prediction:
    return score(pd.DataFrame([features.model_dump()]), customer_id=None)


@app.get("/customers/{customer_id}/churn-risk", response_model=Prediction)
def customer_risk(customer_id: str) -> Prediction:
    frame = load_customer(get_engine(), customer_id)
    if frame.empty:
        raise HTTPException(404, f"Customer {customer_id} not found")
    return score(frame, customer_id)


@app.get("/model/metrics")
def model_metrics() -> dict:
    if not config.METRICS_PATH.exists():
        raise HTTPException(503, "Model not trained yet")
    return json.loads(config.METRICS_PATH.read_text())


@app.get("/monitoring/drift")
def monitoring_drift() -> dict:
    return drift_report(get_engine())


@app.post("/agent/ask")
def agent_ask(body: AgentQuestion) -> dict:
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(503, "Agent disabled: set ANTHROPIC_API_KEY")
    from churn.agent import ask  # lazy: the agent is optional

    try:
        result = ask(body.question)
    except Exception as err:
        raise HTTPException(422, f"Could not answer safely: {err}") from err
    return {"question": result.question, "sql": result.sql, "answer": result.answer,
            "rows": result.rows.to_dict(orient="records")}
