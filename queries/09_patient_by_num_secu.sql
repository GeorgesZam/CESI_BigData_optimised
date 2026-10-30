-- Point lookup on a non-indexed natural key (Patient.Num_Secu).
-- budget_ms: 800
SELECT "Id_patient", "Nom", "Prenom", "Ville"
FROM public."Patient"
WHERE "Num_Secu" = '5571905089387417';
