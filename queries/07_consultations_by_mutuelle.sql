-- Consultations per mutuelle (gold mart).
-- budget_ms: 2000
SELECT nom, consultations
FROM gold.mart_consultations_by_mutuelle
ORDER BY consultations DESC
LIMIT 20;
