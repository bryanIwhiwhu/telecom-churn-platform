"""Agent tests use a fake LLM, so they run in CI without an API key."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from churn import agent


class FakeLLM:
    def __init__(self, sql_replies):
        self.sql_replies = list(sql_replies)
        self.calls = []

    def __call__(self, system, prompt):
        self.calls.append(prompt)
        if "Result rows" in prompt:
            return "Month-to-month contracts churn the most."
        return self.sql_replies.pop(0)


@pytest.mark.parametrize("sql", [
    "DELETE FROM customers",
    "SELECT 1; DROP TABLE customers",
    "UPDATE billing SET monthly_charges = 0",
    "PRAGMA table_info(customers)",
    "",
])
def test_guardrails_block_unsafe_sql(sql):
    with pytest.raises(agent.UnsafeQueryError):
        agent.validate_sql(sql)


def test_guardrails_allow_select_and_cte():
    assert agent.validate_sql("SELECT 1;").startswith("SELECT")
    assert agent.validate_sql("WITH x AS (SELECT 1 AS a) SELECT a FROM x").startswith("WITH")


def test_extract_sql_from_tags_and_fences():
    assert agent.extract_sql("<sql>\nSELECT 1\n</sql>") == "SELECT 1"
    assert agent.extract_sql("```sql\nSELECT 2\n```") == "SELECT 2"


def test_ask_answers_from_data(warehouse):
    llm = FakeLLM(["<sql>SELECT contract_type, ROUND(100.0*SUM(l.churned)/COUNT(*),1) AS rate "
                   "FROM billing b JOIN churn_labels l USING (customer_id) "
                   "GROUP BY contract_type ORDER BY rate DESC</sql>"])
    result = agent.ask("Which contract churns most?", engine=warehouse, llm=llm)
    assert result.rows.iloc[0]["contract_type"] == "Month-to-month"
    assert "Month-to-month" in result.answer


def test_ask_self_corrects_once(warehouse):
    llm = FakeLLM(["<sql>SELECT nope FROM missing_table</sql>",
                   "<sql>SELECT COUNT(*) AS n FROM customers</sql>"])
    result = agent.ask("How many customers?", engine=warehouse, llm=llm)
    assert result.rows.iloc[0]["n"] > 7000
    assert len(result.notes) == 1


def test_readonly_execution_cannot_write(warehouse):
    with pytest.raises(DBAPIError):
        agent.run_readonly(warehouse, "DELETE FROM churn_labels")
    with warehouse.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM churn_labels")).scalar() > 7000
