-- Top 10 diagnostics by consultation count (fact to dimension join).
-- Pre-aggregate the fact table by diagnostic code before the join: 15k groups
-- instead of 1M joined rows.
-- budget_ms: 2000
SELECT d."Diagnostic", sum(c.n) AS consultations
FROM (
    SELECT "Code_diag", count(*) AS n
    FROM public."Consultation"
    GROUP BY "Code_diag"
) c
JOIN public."Diagnostic" d ON d."Code_diag" = c."Code_diag"
GROUP BY d."Diagnostic"
ORDER BY 2 DESC
LIMIT 10;
