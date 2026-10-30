-- Heavy patients: group by patient with a HAVING filter.
-- budget_ms: 2500
SELECT c."Id_patient", count(*) AS consultations
FROM public."Consultation" c
GROUP BY c."Id_patient"
HAVING count(*) >= 15
ORDER BY 2 DESC
LIMIT 50;
