-- Business questions answered in SQL. Run with:  python -m churn.etl --query sql/analysis.sql
-- Each query is separated by a line containing only "-- @query <name>".

-- @query churn_rate_by_contract
-- Which contract types lose the most customers?
SELECT
    b.contract_type,
    COUNT(*)                                   AS customers,
    SUM(l.churned)                             AS churned,
    ROUND(100.0 * SUM(l.churned) / COUNT(*), 1) AS churn_rate_pct
FROM billing b
JOIN churn_labels l ON l.customer_id = b.customer_id
GROUP BY b.contract_type
ORDER BY churn_rate_pct DESC;

-- @query revenue_at_risk_by_internet
-- Monthly recurring revenue lost to churn, by internet product.
SELECT
    s.internet_service,
    ROUND(SUM(CASE WHEN l.churned = 1 THEN b.monthly_charges ELSE 0 END), 2) AS mrr_lost,
    ROUND(SUM(b.monthly_charges), 2)                                          AS mrr_total,
    ROUND(100.0 * SUM(CASE WHEN l.churned = 1 THEN b.monthly_charges ELSE 0 END)
          / SUM(b.monthly_charges), 1)                                        AS pct_mrr_lost
FROM subscriptions s
JOIN billing b      ON b.customer_id = s.customer_id
JOIN churn_labels l ON l.customer_id = s.customer_id
GROUP BY s.internet_service
ORDER BY mrr_lost DESC;

-- @query churn_by_tenure_band
-- How does churn change over the customer lifecycle?
SELECT
    CASE
        WHEN c.tenure_months < 6  THEN '0-5 months'
        WHEN c.tenure_months < 12 THEN '6-11 months'
        WHEN c.tenure_months < 24 THEN '12-23 months'
        WHEN c.tenure_months < 48 THEN '24-47 months'
        ELSE '48+ months'
    END                                         AS tenure_band,
    COUNT(*)                                    AS customers,
    ROUND(100.0 * SUM(l.churned) / COUNT(*), 1) AS churn_rate_pct
FROM customers c
JOIN churn_labels l ON l.customer_id = c.customer_id
GROUP BY tenure_band
ORDER BY MIN(c.tenure_months);

-- @query support_addon_effect
-- Do tech-support subscribers churn less, within the same internet product?
SELECT
    s.internet_service,
    s.tech_support,
    COUNT(*)                                    AS customers,
    ROUND(100.0 * SUM(l.churned) / COUNT(*), 1) AS churn_rate_pct
FROM subscriptions s
JOIN churn_labels l ON l.customer_id = s.customer_id
WHERE s.internet_service <> 'No'
GROUP BY s.internet_service, s.tech_support
ORDER BY s.internet_service, s.tech_support;


-- @query churn_by_payment_method
-- Which payment methods have the highest churn?
SELECT
    b.payment_method,
    COUNT(*)                                    AS customers,
    SUM(l.churned)                             AS churned,
    ROUND(100.0 * SUM(l.churned) / COUNT(*), 1) AS churn_rate_pct
FROM billing b
JOIN churn_labels l ON l.customer_id = b.customer_id
GROUP BY b.payment_method
ORDER BY churn_rate_pct DESC;


-- @query senior_vs_non_senior
-- How does churn and average monthly charges differ between senior and non-senior customers?
SELECT
    CASE WHEN c.senior_citizen = 1 THEN 'Senior'
        ELSE 'Non-senior' 
    END                                                AS segment,
    COUNT(*)                                           AS customers,
    SUM(l.churned)                                     AS churned,
    ROUND(100.0 * SUM(l.churned) / COUNT(*), 1)        AS churn_rate_pct,
    ROUND(AVG(b.monthly_charges), 2)                   AS avg_monthly_charges
FROM billing b
JOIN churn_labels l ON l.customer_id = b.customer_id
JOIN customers c ON c.customer_id = b.customer_id
GROUP BY segment
ORDER BY churn_rate_pct DESC, avg_monthly_charges DESC;