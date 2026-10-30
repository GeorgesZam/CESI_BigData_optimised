-- Point lookup on an unindexed foreign key (Prescription.Num_consultation).
-- budget_ms: 800
SELECT p."Num_consultation", m."Denomination"
FROM public."Prescription" p
JOIN public."Medicaments" m ON m."Code_CIS" = p."Code_CIS"
WHERE p."Num_consultation" = 1059023406;
