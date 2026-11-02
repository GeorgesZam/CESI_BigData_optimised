-- Point lookup on the foreign key (silver consultation, indexed).
-- budget_ms: 800
SELECT num_consultation, consultation_date, motif
FROM silver.consultation
WHERE id_patient = 272
ORDER BY consultation_date DESC
LIMIT 50;
