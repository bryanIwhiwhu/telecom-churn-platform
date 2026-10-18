import pandas as pd
import pytest
from sqlalchemy import text

from churn import config, etl


def test_tables_loaded_with_one_row_per_customer(warehouse):
    raw_rows = len(pd.read_csv(config.RAW_CSV))
    with warehouse.connect() as conn:
        for table in etl.TABLE_COLUMNS:
            assert conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() == raw_rows


def test_feature_view_has_no_nulls(warehouse):
    with warehouse.connect() as conn:
        df = pd.read_sql(text("SELECT * FROM customer_features"), conn)
    assert not df.isna().any().any()
    assert set(df["churned"].unique()) == {0, 1}


def test_blank_total_charges_only_for_new_customers():
    raw = etl.extract()
    raw.loc[raw.index[0], "TotalCharges"] = " "
    raw.loc[raw.index[0], "tenure"] = "12"
    with pytest.raises(etl.DataQualityError):
        etl.transform(raw)


def test_duplicate_ids_rejected():
    raw = etl.extract()
    dup = pd.concat([raw, raw.head(1)], ignore_index=True)
    with pytest.raises(etl.DataQualityError):
        etl.transform(dup)


def test_business_queries_run(warehouse):
    results = etl.run_named_queries(config.ROOT / "sql" / "analysis.sql", warehouse)
    assert set(results) == {"churn_rate_by_contract", "revenue_at_risk_by_internet",
                            "churn_by_tenure_band", "support_addon_effect"}
    contract = results["churn_rate_by_contract"]
    assert contract.iloc[0]["contract_type"] == "Month-to-month"
