-- Prescriptions of one consultation (silver, indexed).
-- budget_ms: 800
SELECT p.num_consultation, m.denomination
FROM silver.prescription p
JOIN silver.medicament m ON m.code_cis = p.code_cis
WHERE p.num_consultation = 1059023406;
