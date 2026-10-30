-- Prescription fact join with the medicament dimension.
-- budget_ms: 2500
SELECT m."Denomination", count(*) AS prescriptions
FROM public."Prescription" p
JOIN public."Medicaments" m ON m."Code_CIS" = p."Code_CIS"
GROUP BY m."Denomination"
ORDER BY 2 DESC
LIMIT 20;
