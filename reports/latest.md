# Database performance report

- Generated: 2026-10-30 12:49:07 UTC
- Database: PostgreSQL 14.24 (Debian 14.24-1.pgdg13+2) on x86_64-pc-linux-gnu, compiled by gcc (Debian 14.2.0-19) 14.2.0, 64-bit
- Size: 352 MB, ~3,674,384 rows
- Host: 4 vCPU, 15.6 GiB RAM, 84.3 GiB free disk of 144.3 GiB
- Runner: Linux 7.0.0-1017-azure / Python 3.12.15
- Method: 1 warm-up run(s), 5 measured run(s), median and p95 wall time

## Measurements (database as restored, no modification)

| Query | Median (ms) | p95 (ms) | Rows | Budget (ms) | Status | Seq scans |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| `consultations_per_month` | 58.0 | 58.3 | 12 | 1200 | ok | Consultation |
| `consultations_by_sexe` | 175.1 | 181.3 | 2 | 1500 | ok | Consultation, Patient |
| `top_diagnostics` | 213.1 | 221.9 | 10 | 2000 | ok | Consultation, Diagnostic |
| `consultations_per_specialite` | 428.9 | 433.0 | 20 | 2500 | ok | Consultation, Professionnel_de_sante, Specialites |
| `top_medicaments_prescrits` | 178.3 | 197.2 | 20 | 2500 | ok | Medicaments, Prescription |
| `patients_with_many_consultations` | 290.4 | 293.8 | 50 | 2500 | ok | Consultation |
| `consultations_by_mutuelle` | 134.2 | 134.6 | 20 | 2000 | ok | Consultation, Mutuelle |
| `consultation_duration_by_weekday` | 360.7 | 381.8 | 7 | 1500 | ok | Consultation |
| `patient_by_num_secu` | 13.2 | 13.8 | 1 | 800 | ok | Patient |
| `consultations_of_one_patient` | 35.2 | 35.8 | 6 | 800 | ok | Consultation |
| `prescriptions_of_one_consultation` | 28.7 | 28.9 | 5 | 800 | ok | Prescription |
| `medicament_search` | 12.6 | 12.7 | 30 | 1200 | ok | Medicaments |

## Compared to the stored baseline

No `bench/baseline.json` yet. Run the workflow manually with `update_baseline = true` to record one.

## Resources

| Resource | Value |
| --- | --- |
| CPU | 4 vCPU |
| RAM | 15.6 GiB |
| Disk | 84.3 GiB free of 144.3 GiB |
| Database size | 352 MB |
| Dump size | 47.0 MB |
| `shared_buffers` | 128MB |
| `work_mem` | 4MB |
| `effective_cache_size` | 4GB |
| `max_parallel_workers_per_gather` | 2 |

## Storage cost estimate

| Stored object | Size (decimal GB) | S3 Standard | S3 Standard-IA | S3 Glacier Deep Archive |
| --- | ---: | ---: | ---: | ---: |
| Database (restored) | 0.369 | $0.0085/mo | $0.0046/mo | $0.0004/mo |
| Dump file | 0.047 | $0.0011/mo | $0.0006/mo | $0.0000/mo |

Prices are us-east-1 list prices per GB-month for storage only. They exclude requests, egress, versioning and any other AWS service. Sizes use decimal GB (10^9 bytes), as AWS bills them.

## Notes

- Timings come from a shared GitHub runner: compare runs from the same job, not absolute values across jobs.
- Queries under about 1 ms are dominated by measurement noise; their ratios are not meaningful.
- `VACUUM (ANALYZE)` runs before the measurement so the planner has real statistics. It does not change data or indexes.
