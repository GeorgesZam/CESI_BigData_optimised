-- Patients with at least 15 consultations (gold mart).
-- budget_ms: 2500
SELECT patient_id, consultations
FROM gold.mart_patients_with_many
ORDER BY consultations DESC
LIMIT 50;
