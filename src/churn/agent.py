"""Natural-language analytics agent: business question -> safe SQL -> answer.

Flow:
  1. The LLM sees the warehouse schema and writes one SELECT query.
  2. Guardrails reject anything that is not a single read-only SELECT.
  3. The query runs inside a read-only transaction with a row cap.
  4. The LLM summarizes the rows in plain business language.

Usage:  ANTHROPIC_API_KEY=... python -m churn.agent "Which contract type churns most?"
"""

from __future__ import annotations

import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from churn import config
from churn.etl import get_engine

FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|truncate|attach|detach|pragma|"
    r"grant|revoke|vacuum|copy|merge|call|exec|execute)\b",
    re.IGNORECASE,
)

SYSTEM_PROMPT = """You are a data analyst for a telecom company. Write ONE SQL SELECT query
that answers the user's question using only this schema:

{schema}

Rules:
- Output only the query inside <sql></sql> tags. No explanation.
- Read-only SELECT (CTEs with WITH are fine). Never modify data.
- Use only the tables and columns listed above. Churned customers have churned = 1.
- Percentages: ROUND(100.0 * x / y, 1). Keep results small (aggregate or LIMIT).
"""

SUMMARY_PROMPT = """Question: {question}

SQL used:
{sql}

Result rows (CSV):
{rows}

Answer the question in 2-4 sentences for a business audience. Use only numbers that
appear in the rows. If the rows do not answer the question, say so."""


class UnsafeQueryError(ValueError):
    """The generated SQL failed a guardrail check."""


class LLM(Protocol):
    def __call__(self, system: str, prompt: str) -> str: ...


@dataclass
class AgentResult:
    question: str
    sql: str
    rows: pd.DataFrame
    answer: str
    notes: list[str] = field(default_factory=list)


# ------------------------------------------------------------- guardrails
def extract_sql(llm_output: str) -> str:
    match = re.search(r"<sql>(.*?)</sql>", llm_output, re.DOTALL | re.IGNORECASE)
    sql = (match.group(1) if match else llm_output).strip()
    return re.sub(r"^```(?:sql)?|```$", "", sql, flags=re.IGNORECASE).strip()


def validate_sql(sql: str) -> str:
    cleaned = re.sub(r"--[^\n]*", "", sql).strip().rstrip(";").strip()
    if not cleaned:
        raise UnsafeQueryError("Empty query")
    if ";" in cleaned:
        raise UnsafeQueryError("Multiple statements are not allowed")
    if not re.match(r"^(select|with)\b", cleaned, re.IGNORECASE):
        raise UnsafeQueryError("Only SELECT queries are allowed")
    if FORBIDDEN.search(cleaned):
        raise UnsafeQueryError("Query contains a forbidden keyword")
    return cleaned


def run_readonly(engine: Engine, sql: str, max_rows: int = config.AGENT_MAX_ROWS) -> pd.DataFrame:
    with engine.connect() as conn:
        if engine.dialect.name == "postgresql":
            conn.execute(text("SET TRANSACTION READ ONLY"))
        elif engine.dialect.name == "sqlite":
            conn.exec_driver_sql("PRAGMA query_only = ON")
        try:
            result = conn.execute(text(sql))
            rows = result.fetchmany(max_rows)
            return pd.DataFrame(rows, columns=list(result.keys()))
        finally:
            if engine.dialect.name == "sqlite":
                conn.exec_driver_sql("PRAGMA query_only = OFF")
            conn.rollback()


# ------------------------------------------------------------------- llm
def schema_description() -> str:
    lines = [ln for ln in config.SCHEMA_SQL.read_text().splitlines()
             if not ln.strip().startswith(("DROP", "--")) and ln.strip()]
    return "\n".join(lines)


def anthropic_llm() -> LLM:
    import anthropic  # imported lazily so tests and the API run without it

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment

    def call(system: str, prompt: str) -> str:
        msg = client.messages.create(
            model=config.LLM_MODEL, max_tokens=800, system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in msg.content if block.type == "text")

    return call


# ----------------------------------------------------------------- agent
def ask(question: str, engine: Engine | None = None, llm: LLM | None = None,
        max_retries: int = 1) -> AgentResult:
    engine = engine or get_engine()
    llm = llm or anthropic_llm()
    system = SYSTEM_PROMPT.format(schema=schema_description())
    prompt, notes = question, []

    for attempt in range(max_retries + 1):
        sql = extract_sql(llm(system, prompt))
        try:
            safe_sql = validate_sql(sql)
            rows = run_readonly(engine, safe_sql)
            break
        except Exception as err:  # guardrail or SQL error: let the model self-correct once
            notes.append(f"attempt {attempt + 1} failed: {err}")
            if attempt == max_retries:
                raise
            prompt = f"{question}\n\nYour previous query failed with: {err}\nWrite a corrected query."

    answer = llm("You explain data clearly and never invent numbers.",
                 SUMMARY_PROMPT.format(question=question, sql=safe_sql,
                                       rows=rows.to_csv(index=False)))
    return AgentResult(question, safe_sql, rows, answer.strip(), notes)


def main(argv: list[str] | None = None, llm_factory: Callable[[], LLM] = anthropic_llm) -> None:
    question = " ".join(argv or sys.argv[1:]) or "Which contract type has the highest churn rate?"
    result = ask(question, llm=llm_factory())
    print(f"SQL:\n{result.sql}\n\nRows:\n{result.rows.to_string(index=False)}\n\nAnswer:\n{result.answer}")


if __name__ == "__main__":
    main()
