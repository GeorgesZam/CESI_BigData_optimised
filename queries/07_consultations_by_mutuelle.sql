-- Reimbursement analysis by mutuelle.
-- Pre-aggregate the fact table by mutuelle first: 100 groups instead of 1M
-- joined rows.
-- budget_ms: 2000
SELECT mu."Nom", sum(c.n) AS consultations
FROM (
    SELECT "Id_mut", count(*) AS n
    FROM public."Consultation"
    GROUP BY "Id_mut"
) c
JOIN public."Mutuelle" mu ON mu."Id_Mut" = c."Id_mut"
GROUP BY mu."Nom"
ORDER BY 2 DESC
LIMIT 20;
