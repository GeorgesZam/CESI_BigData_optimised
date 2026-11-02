-- Prescription fact join with the medicament dimension.
-- Pre-aggregate prescriptions by Code_CIS before the join: 15k groups instead
-- of 1M joined rows.
-- budget_ms: 2500
SELECT m."Denomination", sum(p.n) AS prescriptions
FROM (
    SELECT "Code_CIS", count(*) AS n
    FROM public."Prescription"
    GROUP BY "Code_CIS"
) p
JOIN public."Medicaments" m ON m."Code_CIS" = p."Code_CIS"
GROUP BY m."Denomination"
ORDER BY 2 DESC
LIMIT 20;
