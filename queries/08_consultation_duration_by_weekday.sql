-- Average consultation duration (Heure_fin - Heure_debut) per weekday.
-- budget_ms: 1500
SELECT to_char("Date", 'Day') AS weekday,
       round(avg(extract(epoch FROM ("Heure_fin" - "Heure_debut")) / 60.0), 1) AS avg_minutes,
       count(*) AS consultations
FROM public."Consultation"
WHERE "Heure_fin" > "Heure_debut"
GROUP BY 1
ORDER BY 1;
