-- Join + aggregation over the whole fact table (no index on Consultation.Id_patient).
-- budget_ms: 1500
SELECT p."Sexe", count(*) AS consultations
FROM public."Consultation" c
JOIN public."Patient" p ON p."Id_patient" = c."Id_patient"
GROUP BY p."Sexe"
ORDER BY 2 DESC;
