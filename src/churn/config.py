"""Central configuration. Everything is overridable with environment variables
so the same code runs locally, in Docker, in CI and on Cloud Run."""

from __future__ import annotations

import os
from pathlib import Path


def _project_root() -> Path:
    """Repo root in development; APP_ROOT or the working directory when installed (e.g. in Docker)."""
    if os.getenv("APP_ROOT"):
        return Path(os.environ["APP_ROOT"])
    source_root = Path(__file__).resolve().parents[2]
    return source_root if (source_root / "sql").is_dir() else Path.cwd()


ROOT = _project_root()

RAW_CSV = Path(os.getenv("RAW_CSV", ROOT / "data" / "raw" / "telco_churn.csv"))
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{ROOT / 'data' / 'warehouse.db'}")
MODEL_DIR = Path(os.getenv("MODEL_DIR", ROOT / "models"))
MODEL_PATH = MODEL_DIR / "churn_model.joblib"
METRICS_PATH = MODEL_DIR / "metrics.json"
REFERENCE_STATS_PATH = MODEL_DIR / "reference_stats.json"
SCHEMA_SQL = ROOT / "sql" / "schema.sql"

# LLM agent settings. The key is only read at call time and never logged.
LLM_MODEL = os.getenv("LLM_MODEL", "claude-haiku-4-5-20251001")
AGENT_MAX_ROWS = int(os.getenv("AGENT_MAX_ROWS", "50"))

RANDOM_SEED = 42
