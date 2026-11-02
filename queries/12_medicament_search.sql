-- Free-text search on medicament labels (silver, trigram index).
-- budget_ms: 1200
SELECT code_cis, denomination
FROM silver.medicament
WHERE denomination ILIKE '%doliprane%'
ORDER BY denomination
LIMIT 50;
