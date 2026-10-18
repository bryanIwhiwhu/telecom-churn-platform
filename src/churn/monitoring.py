"""Production monitoring: compare live prediction traffic against training data.

Uses the Population Stability Index (PSI). Rule of thumb:
    PSI < 0.1  stable | 0.1-0.25  watch | > 0.25  investigate / retrain

Usage:  python -m churn.monitoring
"""

from __future__ import annotations

import json
import logging

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from churn import config
from churn.etl import get_engine

log = logging.getLogger("churn.monitoring")
EPS = 1e-6


def psi(expected: np.ndarray, actual: np.ndarray) -> float:
    expected = np.clip(np.asarray(expected, float), EPS, None)
    actual = np.clip(np.asarray(actual, float), EPS, None)
    return float(np.sum((actual - expected) * np.log(actual / expected)))


def status(value: float) -> str:
    return "stable" if value < 0.1 else "watch" if value < 0.25 else "investigate"


def drift_report(engine: Engine, min_rows: int = 30) -> dict:
    ref = json.loads(config.REFERENCE_STATS_PATH.read_text())
    with engine.connect() as conn:
        live = pd.read_sql(text("SELECT * FROM prediction_log"), conn)

    report = {"n_predictions": int(len(live)), "features": {}}
    if len(live) < min_rows:
        report["note"] = f"Need at least {min_rows} logged predictions for a reliable drift check."
        return report

    report["mean_churn_probability"] = round(float(live["churn_probability"].astype(float).mean()), 4)
    for col, spec in ref["numeric"].items():
        edges = np.array(spec["edges"], float)
        edges[0], edges[-1] = -np.inf, np.inf
        counts, _ = np.histogram(live[col].astype(float), bins=edges)
        value = psi(spec["proportions"], counts / counts.sum())
        report["features"][col] = {"psi": round(value, 4), "status": status(value)}
    for col, ref_props in ref["categorical"].items():
        live_props = live[col].value_counts(normalize=True)
        cats = sorted(set(ref_props) | set(live_props.index))
        value = psi([ref_props.get(c, 0) for c in cats], [live_props.get(c, 0) for c in cats])
        report["features"][col] = {"psi": round(value, 4), "status": status(value)}
    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(drift_report(get_engine()), indent=2))
