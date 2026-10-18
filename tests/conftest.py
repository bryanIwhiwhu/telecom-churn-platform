"""Test setup: build an isolated warehouse and model in a temp folder once per session."""

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="churn-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP / 'test.db'}"
os.environ["MODEL_DIR"] = str(_TMP / "models")
os.environ.pop("ANTHROPIC_API_KEY", None)

import pytest  # noqa: E402

from churn import etl, train  # noqa: E402


@pytest.fixture(scope="session")
def warehouse():
    etl.run()
    return etl.get_engine()


@pytest.fixture(scope="session")
def trained(warehouse):
    return train.train()
