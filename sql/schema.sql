-- Normalized schema for the telecom churn warehouse.
-- Portable across SQLite (local dev) and PostgreSQL (docker-compose / Cloud SQL).

DROP VIEW IF EXISTS customer_features;
DROP TABLE IF EXISTS prediction_log;
DROP TABLE IF EXISTS churn_labels;
DROP TABLE IF EXISTS billing;
DROP TABLE IF EXISTS subscriptions;
DROP TABLE IF EXISTS customers;

-- One row per customer: demographics only.
CREATE TABLE customers (
    customer_id     VARCHAR(20) PRIMARY KEY,
    gender          VARCHAR(10) NOT NULL,
    senior_citizen  INTEGER     NOT NULL CHECK (senior_citizen IN (0, 1)),
    has_partner     INTEGER     NOT NULL CHECK (has_partner IN (0, 1)),
    has_dependents  INTEGER     NOT NULL CHECK (has_dependents IN (0, 1)),
    tenure_months   INTEGER     NOT NULL CHECK (tenure_months >= 0)
);

-- One row per customer: which products they subscribe to.
CREATE TABLE subscriptions (
    customer_id        VARCHAR(20) PRIMARY KEY REFERENCES customers(customer_id),
    phone_service      VARCHAR(20) NOT NULL,
    multiple_lines     VARCHAR(20) NOT NULL,
    internet_service   VARCHAR(20) NOT NULL,
    online_security    VARCHAR(20) NOT NULL,
    online_backup      VARCHAR(20) NOT NULL,
    device_protection  VARCHAR(20) NOT NULL,
    tech_support       VARCHAR(20) NOT NULL,
    streaming_tv       VARCHAR(20) NOT NULL,
    streaming_movies   VARCHAR(20) NOT NULL
);

-- One row per customer: contract and billing terms.
CREATE TABLE billing (
    customer_id        VARCHAR(20) PRIMARY KEY REFERENCES customers(customer_id),
    contract_type      VARCHAR(20)   NOT NULL,
    paperless_billing  INTEGER       NOT NULL CHECK (paperless_billing IN (0, 1)),
    payment_method     VARCHAR(40)   NOT NULL,
    monthly_charges    NUMERIC(8, 2) NOT NULL,
    total_charges      NUMERIC(10, 2) NOT NULL
);

-- Target label kept separate so it can never leak into serving features.
CREATE TABLE churn_labels (
    customer_id  VARCHAR(20) PRIMARY KEY REFERENCES customers(customer_id),
    churned      INTEGER NOT NULL CHECK (churned IN (0, 1))
);

-- Every prediction the API serves is logged here for monitoring.
CREATE TABLE prediction_log (
    id               INTEGER PRIMARY KEY,
    created_at       VARCHAR(32)  NOT NULL,
    model_version    VARCHAR(40)  NOT NULL,
    customer_id      VARCHAR(20),
    churn_probability NUMERIC(6, 4) NOT NULL,
    tenure_months    INTEGER,
    monthly_charges  NUMERIC(8, 2),
    contract_type    VARCHAR(20)
);

-- Model-ready view: one wide row per customer, label included for training.
CREATE VIEW customer_features AS
SELECT
    c.customer_id,
    c.gender,
    c.senior_citizen,
    c.has_partner,
    c.has_dependents,
    c.tenure_months,
    s.phone_service,
    s.multiple_lines,
    s.internet_service,
    s.online_security,
    s.online_backup,
    s.device_protection,
    s.tech_support,
    s.streaming_tv,
    s.streaming_movies,
    b.contract_type,
    b.paperless_billing,
    b.payment_method,
    b.monthly_charges,
    b.total_charges,
    l.churned
FROM customers c
JOIN subscriptions s ON s.customer_id = c.customer_id
JOIN billing b       ON b.customer_id = c.customer_id
JOIN churn_labels l  ON l.customer_id = c.customer_id;
