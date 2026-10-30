-- Point lookup on an unindexed foreign key (Consultation.Id_patient).
-- budget_ms: 800
SELECT "Num_consultation", "Date", "Motif"
FROM public."Consultation"
WHERE "Id_patient" = 272
ORDER BY "Date" DESC
LIMIT 50;
