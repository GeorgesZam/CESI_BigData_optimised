-- Consultations of one patient directly on the bucketed fact table.
-- The hash bucket for patient_key 272 is read, the other buckets are pruned.
-- budget_ms: 1500
SELECT count(*) AS consultations
FROM gold.fact_consultation
WHERE patient_key = 272;
