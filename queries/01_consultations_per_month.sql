-- Monthly consultation volume for one year (gold mart).
-- budget_ms: 1200
SELECT month, consultations
FROM gold.mart_consultations_per_month
WHERE month >= DATE '2022-01-01' AND month < DATE '2023-01-01'
ORDER BY month;
