"""Extract-Transform-Load pipeline: raw CSV -> validated, normalized SQL tables.

Usage:
    python -m churn.etl                      # rebuild the warehouse
    python -m churn.etl --query sql/analysis.sql   # run the business queries
"""

from __future__ import annotations

import argparse
import logging
import re
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from churn import config

log = logging.getLogger("churn.etl")

YES_NO_COLUMNS = ["Partner", "Dependents", "PaperlessBilling", "Churn"]

RENAME = {
    "customerID": "customer_id",
    "gender": "gender",
    "SeniorCitizen": "senior_citizen",
    "Partner": "has_partner",
    "Dependents": "has_dependents",
    "tenure": "tenure_months",
    "PhoneService": "phone_service",
    "MultipleLines": "multiple_lines",
    "InternetService": "internet_service",
    "OnlineSecurity": "online_security",
    "OnlineBackup": "online_backup",
    "DeviceProtection": "device_protection",
    "TechSupport": "tech_support",
    "StreamingTV": "streaming_tv",
    "StreamingMovies": "streaming_movies",
    "Contract": "contract_type",
    "PaperlessBilling": "paperless_billing",
    "PaymentMethod": "payment_method",
    "MonthlyCharges": "monthly_charges",
    "TotalCharges": "total_charges",
    "Churn": "churned",
}

TABLE_COLUMNS = {
    "customers": ["customer_id", "gender", "senior_citizen", "has_partner",
                  "has_dependents", "tenure_months"],
    "subscriptions": ["customer_id", "phone_service", "multiple_lines", "internet_service",
                      "online_security", "online_backup", "device_protection",
                      "tech_support", "streaming_tv", "streaming_movies"],
    "billing": ["customer_id", "contract_type", "paperless_billing", "payment_method",
                "monthly_charges", "total_charges"],
    "churn_labels": ["customer_id", "churned"],
}


class DataQualityError(ValueError):
    """Raised when the source data fails a validation check."""


# ---------------------------------------------------------------- extract
def extract(csv_path: Path = config.RAW_CSV) -> pd.DataFrame:
    df = pd.read_csv(csv_path, dtype=str)
    missing = set(RENAME) - set(df.columns)
    if missing:
        raise DataQualityError(f"Source file is missing columns: {sorted(missing)}")
    log.info("Extracted %d rows from %s", len(df), csv_path)
    return df


# -------------------------------------------------------------- transform
def transform(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    df = df.apply(lambda col: col.str.strip())

    # TotalCharges is blank for brand-new customers (tenure 0): nothing billed yet.
    blank_total = df["TotalCharges"].eq("")
    if (df.loc[blank_total, "tenure"].astype(int) != 0).any():
        raise DataQualityError("Blank TotalCharges found for customers with tenure > 0")
    df.loc[blank_total, "TotalCharges"] = "0"

    for col in YES_NO_COLUMNS:
        bad = ~df[col].isin(["Yes", "No"])
        if bad.any():
            raise DataQualityError(f"Unexpected values in {col}: {df.loc[bad, col].unique()}")
        df[col] = (df[col] == "Yes").astype(int)

    df = df.rename(columns=RENAME)[list(RENAME.values())]
    df["senior_citizen"] = df["senior_citizen"].astype(int)
    df["tenure_months"] = df["tenure_months"].astype(int)
    df["monthly_charges"] = df["monthly_charges"].astype(float).round(2)
    df["total_charges"] = df["total_charges"].astype(float).round(2)

    _validate(df)
    log.info("Transformed %d rows (%d blank TotalCharges set to 0)", len(df), int(blank_total.sum()))
    return df


def _validate(df: pd.DataFrame) -> None:
    if df["customer_id"].duplicated().any():
        raise DataQualityError("Duplicate customer_id values")
    if df.isna().any().any():
        cols = df.columns[df.isna().any()].tolist()
        raise DataQualityError(f"Null values in: {cols}")
    if (df["monthly_charges"] <= 0).any():
        raise DataQualityError("Non-positive monthly_charges")
    if (df["tenure_months"] < 0).any():
        raise DataQualityError("Negative tenure")


# ------------------------------------------------------------------- load
def get_engine(url: str = config.DATABASE_URL) -> Engine:
    return create_engine(url, future=True)


def apply_schema(engine: Engine, schema_path: Path = config.SCHEMA_SQL) -> None:
    sql = schema_path.read_text()
    if engine.dialect.name == "postgresql":
        sql = re.sub(r"\bid\s+INTEGER PRIMARY KEY", "id SERIAL PRIMARY KEY", sql)
        sql = sql.replace("DROP TABLE IF EXISTS customers;", "DROP TABLE IF EXISTS customers CASCADE;")
    statements = [s.strip() for s in sql.split(";") if _strip_comments(s).strip()]
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))


def _strip_comments(sql: str) -> str:
    return "\n".join(line for line in sql.splitlines() if not line.strip().startswith("--"))


def load(df: pd.DataFrame, engine: Engine) -> dict[str, int]:
    apply_schema(engine)
    counts = {}
    with engine.begin() as conn:  # all-or-nothing load
        for table, cols in TABLE_COLUMNS.items():
            df[cols].to_sql(table, conn, if_exists="append", index=False)
            counts[table] = len(df)
    log.info("Loaded tables: %s", counts)
    return counts


def run(csv_path: Path = config.RAW_CSV, url: str = config.DATABASE_URL) -> dict[str, int]:
    engine = get_engine(url)
    return load(transform(extract(csv_path)), engine)


# ---------------------------------------------------------------- queries
def run_named_queries(path: Path, engine: Engine) -> dict[str, pd.DataFrame]:
    blocks = re.split(r"^-- @query (\w+)\s*$", path.read_text(), flags=re.MULTILINE)
    results = {}
    with engine.connect() as conn:
        for name, sql in zip(blocks[1::2], blocks[2::2], strict=True):
            results[name] = pd.read_sql(text(_strip_comments(sql).strip().rstrip(";")), conn)
    return results


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", type=Path, help="Run named queries from a .sql file instead of ETL")
    args = parser.parse_args()
    if args.query:
        for name, frame in run_named_queries(args.query, get_engine()).items():
            print(f"\n== {name} ==\n{frame.to_string(index=False)}")
    else:
        run()


if __name__ == "__main__":
    main()
