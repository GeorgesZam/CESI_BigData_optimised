-- Top 10 diagnostics by consultation count (fact to dimension join).
-- budget_ms: 2000
SELECT d."Diagnostic", count(*) AS consultations
FROM public."Consultation" c
JOIN public."Diagnostic" d ON d."Code_diag" = c."Code_diag"
GROUP BY d."Diagnostic"
ORDER BY 2 DESC
LIMIT 10;
