-- Average consultation duration per weekday (gold mart).
-- budget_ms: 1500
SELECT weekday, avg_minutes, consultations
FROM gold.mart_duration_by_weekday
ORDER BY weekday;
