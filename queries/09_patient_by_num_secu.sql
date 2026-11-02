-- Point lookup on the natural key (silver patient, indexed).
-- budget_ms: 800
SELECT patient_id, nom, prenom, ville
FROM silver.patient
WHERE num_secu = '5571905089387417';
