# Query catalogue

Every query measured by the benchmark lives in its own file. To add, remove or
rewrite a query, edit the files here: the benchmark reads the whole folder, and the
file contents are hashed into `bench/baseline.json`. When the catalogue changes, the
baseline comparison is skipped until a new baseline is recorded.

Each file starts with a purpose comment and a `-- budget_ms: <n>` line. The query
name is the file name without its numeric prefix.

| # | Query | What it exercises | Budget |
| ---: | --- | --- | ---: |
| 01 | `consultations_per_month` | Range filter on `Consultation.Date`, monthly aggregation | 1200 ms |
| 02 | `consultations_by_sexe` | Join `Consultation` → `Patient`, count per sex | 1500 ms |
| 03 | `top_diagnostics` | Join `Consultation` → `Diagnostic`, top 10 | 2000 ms |
| 04 | `consultations_per_specialite` | Three-table join `Consultation` → `Professionnel_de_sante` → `Specialites` | 2500 ms |
| 05 | `top_medicaments_prescrits` | Join `Prescription` → `Medicaments`, top 20 | 2500 ms |
| 06 | `patients_with_many_consultations` | Group by patient with a `HAVING` filter | 2500 ms |
| 07 | `consultations_by_mutuelle` | Join `Consultation` → `Mutuelle` | 2000 ms |
| 08 | `consultation_duration_by_weekday` | Time difference `Heure_fin - Heure_debut`, average per weekday | 1500 ms |
| 09 | `patient_by_num_secu` | Point lookup on the natural key `Patient.Num_Secu` | 800 ms |
| 10 | `consultations_of_one_patient` | Point lookup on the foreign key `Consultation.Id_patient` | 800 ms |
| 11 | `prescriptions_of_one_consultation` | Point lookup on the foreign key `Prescription.Num_consultation` | 800 ms |
| 12 | `medicament_search` | Free-text `ILIKE` search on medicament labels | 1200 ms |

Queries 01 to 08 cover reporting and analytics. Queries 09 to 12 cover application
screens: patient record, consultation history, prescription detail, drug search.

The parameters are fixed values taken from the real data (year 2022, patient 272,
consultation 1059023406, social security number 5571905089387417, "doliprane"), so
every query returns rows instead of an empty result.

Not covered yet: writes, window functions, CTEs, deep pagination and concurrent
load.
