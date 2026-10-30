-- Three-table join: Consultation -> Professionnel_de_sante -> Specialites.
-- budget_ms: 2500
SELECT s."Specialite", count(*) AS consultations
FROM public."Consultation" c
JOIN public."Professionnel_de_sante" pr ON pr."Identifiant" = c."Id_prof_sante"
JOIN public."Specialites" s ON s."Code_specialite" = pr."Code_specialite"
GROUP BY s."Specialite"
ORDER BY 2 DESC
LIMIT 20;
