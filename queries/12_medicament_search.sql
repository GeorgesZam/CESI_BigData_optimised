-- Free-text search on the medicament label (no trigram index).
-- budget_ms: 1200
SELECT "Code_CIS", "Denomination"
FROM public."Medicaments"
WHERE "Denomination" ILIKE '%doliprane%'
ORDER BY "Denomination"
LIMIT 50;
