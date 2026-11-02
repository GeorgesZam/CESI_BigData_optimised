-- Top 20 medicaments by prescription count (gold mart).
-- budget_ms: 2500
SELECT denomination, prescriptions
FROM gold.mart_top_medicaments
ORDER BY prescriptions DESC
LIMIT 20;
