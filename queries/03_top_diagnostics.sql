-- Top 10 diagnostics by consultation count (gold mart).
-- budget_ms: 2000
SELECT diagnostic, consultations
FROM gold.mart_top_diagnostics
ORDER BY consultations DESC
LIMIT 10;
