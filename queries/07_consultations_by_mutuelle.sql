-- Reimbursement analysis by mutuelle.
-- budget_ms: 2000
SELECT mu."Nom", count(*) AS consultations
FROM public."Consultation" c
JOIN public."Mutuelle" mu ON mu."Id_Mut" = c."Id_mut"
GROUP BY mu."Nom"
ORDER BY 2 DESC
LIMIT 20;
