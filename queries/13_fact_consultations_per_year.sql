-- Count consultations for one year on the partitioned fact table.
-- The planner prunes to the single yearly partition.
-- budget_ms: 1500
SELECT count(*) AS consultations
FROM gold.fact_consultation
WHERE date_key >= DATE '2022-01-01' AND date_key < DATE '2023-01-01';
