-- Average consultation duration (Heure_fin - Heure_debut) per weekday.
-- budget_ms: 1500
SELECT CASE extract(dow FROM "Date")
           WHEN 0 THEN 'Sunday'
           WHEN 1 THEN 'Monday'
           WHEN 2 THEN 'Tuesday'
           WHEN 3 THEN 'Wednesday'
           WHEN 4 THEN 'Thursday'
           WHEN 5 THEN 'Friday'
           WHEN 6 THEN 'Saturday'
       END AS weekday,
       round(avg((extract(epoch FROM "Heure_fin") - extract(epoch FROM "Heure_debut")) / 60.0), 1) AS avg_minutes,
       count(*) AS consultations
FROM public."Consultation"
WHERE "Heure_fin" > "Heure_debut"
GROUP BY 1
ORDER BY 1;
