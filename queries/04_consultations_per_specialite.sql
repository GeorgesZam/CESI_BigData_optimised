-- Consultations per specialty (gold mart).
-- budget_ms: 2500
SELECT specialite, consultations
FROM gold.mart_consultations_per_specialite
ORDER BY consultations DESC
LIMIT 20;
