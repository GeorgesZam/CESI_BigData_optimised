-- Bronze layer: raw tables, unchanged, moved out of public.
CREATE SCHEMA IF NOT EXISTS bronze;

DO $$
DECLARE
    table_name text;
BEGIN
    FOR table_name IN
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public'
          AND tablename IN (
              'AAAA', 'Adher', 'Consultation', 'Diagnostic', 'Laboratoire',
              'Medicaments', 'Mutuelle', 'Patient', 'Prescription',
              'Professionnel_de_sante', 'Salle', 'Specialites', 'date'
          )
    LOOP
        EXECUTE format('ALTER TABLE public.%I SET SCHEMA bronze', table_name);
    END LOOP;
END $$;

CREATE TABLE IF NOT EXISTS bronze.ingestion_log (
    layer text NOT NULL,
    object_name text NOT NULL,
    row_count bigint NOT NULL,
    loaded_at timestamptz NOT NULL DEFAULT now()
);

TRUNCATE bronze.ingestion_log;
INSERT INTO bronze.ingestion_log (layer, object_name, row_count)
SELECT 'bronze', 'Patient', count(*) FROM bronze."Patient"
UNION ALL SELECT 'bronze', 'Consultation', count(*) FROM bronze."Consultation"
UNION ALL SELECT 'bronze', 'Prescription', count(*) FROM bronze."Prescription"
UNION ALL SELECT 'bronze', 'Professionnel_de_sante', count(*) FROM bronze."Professionnel_de_sante"
UNION ALL SELECT 'bronze', 'Medicaments', count(*) FROM bronze."Medicaments"
UNION ALL SELECT 'bronze', 'Diagnostic', count(*) FROM bronze."Diagnostic"
UNION ALL SELECT 'bronze', 'Mutuelle', count(*) FROM bronze."Mutuelle"
UNION ALL SELECT 'bronze', 'Specialites', count(*) FROM bronze."Specialites"
UNION ALL SELECT 'bronze', 'Salle', count(*) FROM bronze."Salle"
UNION ALL SELECT 'bronze', 'Adher', count(*) FROM bronze."Adher"
UNION ALL SELECT 'bronze', 'Laboratoire', count(*) FROM bronze."Laboratoire";
