-- Monthly consultation volume for one year (range scan on Consultation.Date).
-- budget_ms: 1200
SELECT date_trunc('month', "Date")::date AS month,
       count(*) AS consultations
FROM public."Consultation"
WHERE "Date" >= DATE '2022-01-01' AND "Date" < DATE '2023-01-01'
GROUP BY 1
ORDER BY 1;
