"""Train, compare and persist the churn model.

Usage:  python -m churn.train
Writes models/churn_model.joblib, models/metrics.json, models/reference_stats.json
and charts under reports/.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score, roc_curve
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from churn import config
from churn.etl import get_engine
from churn.features import CATEGORICAL, FEATURES, NUMERIC, TARGET, load_training_frame

log = logging.getLogger("churn.train")


def build_candidates() -> dict[str, Pipeline]:
    linear_prep = ColumnTransformer([
        ("num", StandardScaler(), NUMERIC),
        ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
    ])
    tree_prep = ColumnTransformer([
        ("num", "passthrough", NUMERIC),
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL),
    ])
    return {
        "logistic_regression": Pipeline([
            ("prep", linear_prep),
            ("model", LogisticRegression(max_iter=2000, class_weight="balanced")),
        ]),
        "gradient_boosting": Pipeline([
            ("prep", tree_prep),
            ("model", HistGradientBoostingClassifier(
                learning_rate=0.05, max_depth=4, max_iter=300,
                class_weight="balanced", random_state=config.RANDOM_SEED)),
        ]),
    }


def lift_at_top(y_true: np.ndarray, scores: np.ndarray, fraction: float = 0.1) -> float:
    """How much more churn is in the top-scored X% than in the base population."""
    k = max(1, int(len(scores) * fraction))
    top = np.argsort(scores)[::-1][:k]
    return float(y_true[top].mean() / y_true.mean())


def reference_stats(X: pd.DataFrame) -> dict:
    """Training-time feature distributions, used by monitoring to detect drift."""
    stats = {"numeric": {}, "categorical": {}}
    for col in ["tenure_months", "monthly_charges"]:
        edges = np.quantile(X[col], np.linspace(0, 1, 11)).tolist()
        counts, _ = np.histogram(X[col], bins=edges)
        stats["numeric"][col] = {"edges": edges, "proportions": (counts / counts.sum()).tolist()}
    stats["categorical"]["contract_type"] = X["contract_type"].value_counts(normalize=True).to_dict()
    return stats


def save_charts(df: pd.DataFrame, y_test: np.ndarray, scores: np.ndarray) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        log.warning("matplotlib not installed; skipping charts")
        return
    out = config.ROOT / "reports"
    out.mkdir(exist_ok=True)

    rate = df.groupby("contract_type")[TARGET].mean().sort_values() * 100
    fig, ax = plt.subplots(figsize=(6, 3.2))
    ax.barh(rate.index, rate.values, color="#2b6cb0")
    ax.set_xlabel("Churn rate (%)")
    ax.set_title("Month-to-month customers churn most")
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    fig.tight_layout()
    fig.savefig(out / "churn_by_contract.png", dpi=150)
    plt.close(fig)

    fpr, tpr, _ = roc_curve(y_test, scores)
    fig, ax = plt.subplots(figsize=(4, 4))
    ax.plot(fpr, tpr, color="#2b6cb0", label=f"Model (AUC {roc_auc_score(y_test, scores):.3f})")
    ax.plot([0, 1], [0, 1], color="#999999", linestyle="--", label="Random")
    ax.set_xlabel("False positive rate")
    ax.set_ylabel("True positive rate")
    ax.set_title("ROC curve, held-out test set")
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    fig.savefig(out / "roc_curve.png", dpi=150)
    plt.close(fig)


def train() -> dict:
    df = load_training_frame(get_engine())
    X, y = df[FEATURES], df[TARGET].to_numpy()
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=config.RANDOM_SEED)

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=config.RANDOM_SEED)
    cv_scores = {}
    for name, pipe in build_candidates().items():
        scores = cross_val_score(pipe, X_train, y_train, cv=cv, scoring="roc_auc")
        cv_scores[name] = {"mean": round(float(scores.mean()), 4), "std": round(float(scores.std()), 4)}
        log.info("%s CV ROC-AUC %.4f ± %.4f", name, scores.mean(), scores.std())

    best_name = max(cv_scores, key=lambda n: cv_scores[n]["mean"])
    best = build_candidates()[best_name].fit(X_train, y_train)
    test_scores = best.predict_proba(X_test)[:, 1]

    version = datetime.now(UTC).strftime("%Y%m%d%H%M%S") + f"-{best_name}"
    metrics = {
        "model_version": version,
        "selected_model": best_name,
        "cv_roc_auc": cv_scores,
        "test_roc_auc": round(float(roc_auc_score(y_test, test_scores)), 4),
        "test_pr_auc": round(float(average_precision_score(y_test, test_scores)), 4),
        "test_lift_top_decile": round(lift_at_top(y_test, test_scores), 2),
        "base_churn_rate": round(float(y.mean()), 4),
        "n_train": int(len(y_train)),
        "n_test": int(len(y_test)),
    }

    config.MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({"pipeline": best, "version": version, "features": FEATURES}, config.MODEL_PATH)
    config.METRICS_PATH.write_text(json.dumps(metrics, indent=2))
    config.REFERENCE_STATS_PATH.write_text(json.dumps(reference_stats(X_train), indent=2))
    save_charts(df, y_test, test_scores)
    log.info("Saved %s: %s", config.MODEL_PATH, metrics)
    return metrics


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    print(json.dumps(train(), indent=2))
