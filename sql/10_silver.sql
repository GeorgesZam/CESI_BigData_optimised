-- Silver layer: cleaned, typed and constrained tables.
CREATE EXTENSION IF NOT EXISTS pg_trgm;
DROP SCHEMA IF EXISTS silver CASCADE;
CREATE SCHEMA silver;

CREATE TABLE silver.patient (
    patient_id integer PRIMARY KEY,
    nom text,
    prenom text,
    sexe text,
    adresse text,
    ville text,
    code_postal text,
    pays text,
    email text,
    tel text,
    birth_date date,
    age integer,
    num_secu text,
    groupe_sanguin text,
    poids_kg numeric(5,1),
    taille_cm integer
);

INSERT INTO silver.patient
SELECT
    "Id_patient",
    NULLIF(trim("Nom"), ''),
    NULLIF(trim("Prenom"), ''),
    NULLIF(lower(trim("Sexe")), ''),
    NULLIF(trim("Adresse"), ''),
    NULLIF(trim("Ville"), ''),
    NULLIF(trim("Code_postal"), ''),
    NULLIF(trim("Pays"), ''),
    NULLIF(trim("EMail"), ''),
    NULLIF(trim("Tel"), ''),
    to_date("Date", 'MM/DD/YYYY'),
    "Age",
    NULLIF(trim("Num_Secu"), ''),
    NULLIF(trim("Groupe_sanguin"), ''),
    "Poid"::numeric,
    "Taille"::integer
FROM bronze."Patient";

CREATE TABLE silver.diagnostic (
    code_diag text PRIMARY KEY,
    diagnostic text
);

INSERT INTO silver.diagnostic
SELECT trim("Code_diag"), NULLIF(trim("Diagnostic"), '')
FROM bronze."Diagnostic";

CREATE TABLE silver.mutuelle (
    id_mut integer PRIMARY KEY,
    nom text,
    adresse text
);

INSERT INTO silver.mutuelle
SELECT "Id_Mut", NULLIF(trim("Nom"), ''), NULLIF(trim("Adresse"), '')
FROM bronze."Mutuelle";

CREATE TABLE silver.specialite (
    code_specialite text PRIMARY KEY,
    fonction text,
    specialite text
);

INSERT INTO silver.specialite
SELECT trim("Code_specialite"), NULLIF(trim("Fonction"), ''), NULLIF(trim("Specialite"), '')
FROM bronze."Specialites";

CREATE TABLE silver.professionnel (
    identifiant text PRIMARY KEY,
    civilite text,
    categorie_professionnelle text,
    nom text,
    prenom text,
    profession text,
    type_identifiant text,
    code_specialite text
);

INSERT INTO silver.professionnel
SELECT
    trim("Identifiant"),
    NULLIF(trim("Civilite"), ''),
    NULLIF(trim("Categorie_professionnelle"), ''),
    NULLIF(trim("Nom"), ''),
    NULLIF(trim("Prenom"), ''),
    NULLIF(trim("Profession"), ''),
    NULLIF(trim("Type_identifiant"), ''),
    trim("Code_specialite")
FROM bronze."Professionnel_de_sante";

CREATE TABLE silver.medicament (
    code_cis text PRIMARY KEY,
    denomination text,
    forme_pharmaceutique text,
    voies_administration text,
    statut_administratif text,
    type_procedure text,
    etat_commercialisation text,
    date_amm date,
    statut_bdm text,
    num_autorisation_europeenne text,
    titulaire text,
    surveillance_renforcee boolean
);

INSERT INTO silver.medicament
SELECT
    trim("Code_CIS"),
    NULLIF(trim("Denomination"), ''),
    NULLIF(trim("Forme_pharmaceutique"), ''),
    NULLIF(trim("Voies_d_administration"), ''),
    NULLIF(trim("Statut_administratif"), ''),
    NULLIF(trim("Type_de_procedure"), ''),
    NULLIF(trim("Etat_de_commercialisation"), ''),
    to_date(NULLIF(trim("Date_AMM"), ''), 'DD/MM/YYYY'),
    NULLIF(trim("StatutBdm"), ''),
    NULLIF(trim("Num_autorisation_europeenne"), ''),
    NULLIF(trim("Titulaire"), ''),
    CASE
        WHEN lower(trim("Surveillance_renforcee")) = 'oui' THEN true
        WHEN lower(trim("Surveillance_renforcee")) = 'non' THEN false
    END
FROM bronze."Medicaments";

CREATE TABLE silver.laboratoire (
    id_labo integer PRIMARY KEY,
    laboratoire text,
    pays text
);

INSERT INTO silver.laboratoire
SELECT "Id_labo", NULLIF(trim("Laboratoire"), ''), NULLIF(trim("Pays"), '')
FROM bronze."Laboratoire";

CREATE TABLE silver.consultation (
    num_consultation integer PRIMARY KEY,
    id_mut integer REFERENCES silver.mutuelle (id_mut),
    id_patient integer REFERENCES silver.patient (patient_id),
    id_prof_sante text REFERENCES silver.professionnel (identifiant),
    code_diag text REFERENCES silver.diagnostic (code_diag),
    motif text,
    consultation_date date,
    heure_debut time,
    heure_fin time,
    duration_minutes numeric(8,2)
);

INSERT INTO silver.consultation
SELECT
    "Num_consultation",
    "Id_mut",
    "Id_patient",
    trim("Id_prof_sante"),
    trim("Code_diag"),
    NULLIF(trim("Motif"), ''),
    "Date",
    "Heure_debut",
    "Heure_fin",
    round((extract(epoch FROM ("Heure_fin" - "Heure_debut")) / 60.0)::numeric, 2)
FROM bronze."Consultation";

CREATE TABLE silver.prescription (
    prescription_id bigserial PRIMARY KEY,
    num_consultation integer NOT NULL REFERENCES silver.consultation (num_consultation),
    code_cis text NOT NULL REFERENCES silver.medicament (code_cis)
);

INSERT INTO silver.prescription (num_consultation, code_cis)
SELECT p."Num_consultation", trim(p."Code_CIS")
FROM bronze."Prescription" p
WHERE EXISTS (
    SELECT 1 FROM silver.consultation c WHERE c.num_consultation = p."Num_consultation"
)
AND EXISTS (
    SELECT 1 FROM silver.medicament m WHERE m.code_cis = trim(p."Code_CIS")
);

CREATE TABLE silver.adher (
    adher_id bigserial PRIMARY KEY,
    id_patient integer NOT NULL REFERENCES silver.patient (patient_id),
    id_mut integer NOT NULL REFERENCES silver.mutuelle (id_mut)
);

INSERT INTO silver.adher (id_patient, id_mut)
SELECT a."Id_patient", a."Id_mut"
FROM bronze."Adher" a
WHERE EXISTS (SELECT 1 FROM silver.patient p WHERE p.patient_id = a."Id_patient")
AND EXISTS (SELECT 1 FROM silver.mutuelle m WHERE m.id_mut = a."Id_mut");

CREATE TABLE silver.salle (
    id_salle text PRIMARY KEY,
    num_consultation integer REFERENCES silver.consultation (num_consultation),
    code_bloc text,
    num_etage text,
    num_salle text
);

INSERT INTO silver.salle
SELECT trim(s."Id_salle"), s."Num_consultation", NULLIF(trim(s."Code_bloc"), ''),
       NULLIF(trim(s."Num_etage"), ''), NULLIF(trim(s."Num_salle"), '')
FROM bronze."Salle" s
WHERE EXISTS (
    SELECT 1 FROM silver.consultation c WHERE c.num_consultation = s."Num_consultation"
);

CREATE INDEX patient_num_secu_idx ON silver.patient (num_secu);
CREATE INDEX patient_ville_idx ON silver.patient (ville);
CREATE INDEX consultation_date_idx ON silver.consultation (consultation_date);
CREATE INDEX consultation_patient_idx ON silver.consultation (id_patient);
CREATE INDEX consultation_mutuelle_idx ON silver.consultation (id_mut);
CREATE INDEX consultation_prof_idx ON silver.consultation (id_prof_sante);
CREATE INDEX consultation_diag_idx ON silver.consultation (code_diag);
CREATE INDEX prescription_consultation_idx ON silver.prescription (num_consultation);
CREATE INDEX prescription_cis_idx ON silver.prescription (code_cis);
CREATE INDEX professionnel_specialite_idx ON silver.professionnel (code_specialite);
CREATE INDEX adher_patient_idx ON silver.adher (id_patient);
CREATE INDEX adher_mutuelle_idx ON silver.adher (id_mut);
CREATE INDEX salle_consultation_idx ON silver.salle (num_consultation);
CREATE INDEX medicament_denomination_trgm_idx ON silver.medicament USING gin (denomination gin_trgm_ops);
