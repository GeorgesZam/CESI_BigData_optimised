-- Gold layer: dimensions, facts and business marts used by the queries.
DROP SCHEMA IF EXISTS gold CASCADE;
CREATE SCHEMA gold;

CREATE TABLE gold.dim_date AS
SELECT
    day::date AS date_key,
    extract(year FROM day)::int AS year,
    extract(quarter FROM day)::int AS quarter,
    extract(month FROM day)::int AS month,
    extract(day FROM day)::int AS day,
    extract(isodow FROM day)::int AS iso_dow,
    trim(to_char(day, 'Day')) AS weekday
FROM generate_series(
    (SELECT min(consultation_date) FROM silver.consultation),
    (SELECT max(consultation_date) FROM silver.consultation),
    interval '1 day'
) AS day;
ALTER TABLE gold.dim_date ADD PRIMARY KEY (date_key);

CREATE TABLE gold.dim_patient AS
SELECT patient_id, sexe, age, ville, birth_date
FROM silver.patient;
ALTER TABLE gold.dim_patient ADD PRIMARY KEY (patient_id);

CREATE TABLE gold.dim_professionnel AS
SELECT identifiant AS prof_id, code_specialite, nom, profession
FROM silver.professionnel;
ALTER TABLE gold.dim_professionnel ADD PRIMARY KEY (prof_id);
CREATE INDEX dim_professionnel_specialite_idx ON gold.dim_professionnel (code_specialite);

CREATE TABLE gold.dim_specialite AS
SELECT code_specialite, specialite
FROM silver.specialite;
ALTER TABLE gold.dim_specialite ADD PRIMARY KEY (code_specialite);

CREATE TABLE gold.dim_diagnostic AS
SELECT code_diag, diagnostic
FROM silver.diagnostic;
ALTER TABLE gold.dim_diagnostic ADD PRIMARY KEY (code_diag);

CREATE TABLE gold.dim_medicament AS
SELECT code_cis, denomination, forme_pharmaceutique
FROM silver.medicament;
ALTER TABLE gold.dim_medicament ADD PRIMARY KEY (code_cis);

CREATE TABLE gold.dim_mutuelle AS
SELECT id_mut, nom
FROM silver.mutuelle;
ALTER TABLE gold.dim_mutuelle ADD PRIMARY KEY (id_mut);

CREATE TABLE gold.fact_consultation AS
SELECT
    num_consultation,
    consultation_date AS date_key,
    id_patient AS patient_key,
    id_prof_sante AS prof_key,
    id_mut AS mutuelle_key,
    code_diag AS diag_key,
    duration_minutes
FROM silver.consultation;
ALTER TABLE gold.fact_consultation ADD PRIMARY KEY (num_consultation);
ALTER TABLE gold.fact_consultation
    ADD CONSTRAINT fact_consultation_date_fkey FOREIGN KEY (date_key) REFERENCES gold.dim_date (date_key),
    ADD CONSTRAINT fact_consultation_patient_fkey FOREIGN KEY (patient_key) REFERENCES gold.dim_patient (patient_id),
    ADD CONSTRAINT fact_consultation_prof_fkey FOREIGN KEY (prof_key) REFERENCES gold.dim_professionnel (prof_id),
    ADD CONSTRAINT fact_consultation_mutuelle_fkey FOREIGN KEY (mutuelle_key) REFERENCES gold.dim_mutuelle (id_mut),
    ADD CONSTRAINT fact_consultation_diag_fkey FOREIGN KEY (diag_key) REFERENCES gold.dim_diagnostic (code_diag);
CREATE INDEX fact_consultation_date_idx ON gold.fact_consultation (date_key);
CREATE INDEX fact_consultation_patient_idx ON gold.fact_consultation (patient_key);
CREATE INDEX fact_consultation_prof_idx ON gold.fact_consultation (prof_key);
CREATE INDEX fact_consultation_mutuelle_idx ON gold.fact_consultation (mutuelle_key);
CREATE INDEX fact_consultation_diag_idx ON gold.fact_consultation (diag_key);

CREATE TABLE gold.fact_prescription AS
SELECT prescription_id, num_consultation, code_cis AS medicament_key
FROM silver.prescription;
ALTER TABLE gold.fact_prescription ADD PRIMARY KEY (prescription_id);
ALTER TABLE gold.fact_prescription
    ADD CONSTRAINT fact_prescription_consultation_fkey FOREIGN KEY (num_consultation) REFERENCES gold.fact_consultation (num_consultation),
    ADD CONSTRAINT fact_prescription_medicament_fkey FOREIGN KEY (medicament_key) REFERENCES gold.dim_medicament (code_cis);
CREATE INDEX fact_prescription_consultation_idx ON gold.fact_prescription (num_consultation);
CREATE INDEX fact_prescription_medicament_idx ON gold.fact_prescription (medicament_key);

CREATE TABLE gold.mart_consultations_per_month AS
SELECT date_trunc('month', date_key)::date AS month, count(*) AS consultations
FROM gold.fact_consultation
GROUP BY 1;
ALTER TABLE gold.mart_consultations_per_month ADD PRIMARY KEY (month);

CREATE TABLE gold.mart_consultations_by_sexe AS
SELECT p.sexe, count(*) AS consultations
FROM gold.fact_consultation f
JOIN gold.dim_patient p ON p.patient_id = f.patient_key
GROUP BY p.sexe;
ALTER TABLE gold.mart_consultations_by_sexe ADD PRIMARY KEY (sexe);

CREATE TABLE gold.mart_top_diagnostics AS
SELECT d.diagnostic, count(*) AS consultations
FROM gold.fact_consultation f
JOIN gold.dim_diagnostic d ON d.code_diag = f.diag_key
GROUP BY d.diagnostic;
ALTER TABLE gold.mart_top_diagnostics ADD PRIMARY KEY (diagnostic);

CREATE TABLE gold.mart_consultations_per_specialite AS
SELECT s.specialite, count(*) AS consultations
FROM gold.fact_consultation f
JOIN gold.dim_professionnel pr ON pr.prof_id = f.prof_key
JOIN gold.dim_specialite s ON s.code_specialite = pr.code_specialite
GROUP BY s.specialite;
ALTER TABLE gold.mart_consultations_per_specialite ADD PRIMARY KEY (specialite);

CREATE TABLE gold.mart_top_medicaments AS
SELECT m.denomination, count(*) AS prescriptions
FROM gold.fact_prescription p
JOIN gold.dim_medicament m ON m.code_cis = p.medicament_key
GROUP BY m.denomination;
ALTER TABLE gold.mart_top_medicaments ADD PRIMARY KEY (denomination);

CREATE TABLE gold.mart_patients_with_many AS
SELECT patient_key AS patient_id, count(*) AS consultations
FROM gold.fact_consultation
GROUP BY patient_key
HAVING count(*) >= 15;
ALTER TABLE gold.mart_patients_with_many ADD PRIMARY KEY (patient_id);

CREATE TABLE gold.mart_consultations_by_mutuelle AS
SELECT mu.nom, count(*) AS consultations
FROM gold.fact_consultation f
JOIN gold.dim_mutuelle mu ON mu.id_mut = f.mutuelle_key
GROUP BY mu.nom;
ALTER TABLE gold.mart_consultations_by_mutuelle ADD PRIMARY KEY (nom);

CREATE TABLE gold.mart_duration_by_weekday AS
SELECT d.iso_dow, d.weekday, round(avg(f.duration_minutes), 1) AS avg_minutes, count(*) AS consultations
FROM gold.fact_consultation f
JOIN gold.dim_date d ON d.date_key = f.date_key
GROUP BY d.iso_dow, d.weekday;
ALTER TABLE gold.mart_duration_by_weekday ADD PRIMARY KEY (iso_dow);
