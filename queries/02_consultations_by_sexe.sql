-- Consultation count per sex (gold mart).
-- budget_ms: 1500
SELECT sexe, consultations
FROM gold.mart_consultations_by_sexe
ORDER BY consultations DESC;
