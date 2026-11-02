# Database performance report

- Generated: 2026-11-02 13:30:59 UTC
- Database: PostgreSQL 14.24 (Debian 14.24-1.pgdg13+2) on x86_64-pc-linux-gnu, compiled by gcc (Debian 14.2.0-19) 14.2.0, 64-bit
- Size: 352 MB, ~3,674,384 rows
- Host: 4 vCPU, 15.6 GiB RAM, 84.3 GiB free disk of 144.3 GiB
- Runner: Linux 7.0.0-1017-azure / Python 3.12.15
- Method: 1 warm-up run(s), 3 measured run(s), median and p95 wall time

## Measurements (database as restored, no modification)

Budgets are 2.5x the stored baseline median, rounded up to 50 ms with a floor of 100 ms. The SQL budget applies when no baseline exists.

| Query | Median (ms) | p95 (ms) | Rows | Budget (ms) | Status | Seq scans |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| `consultations_per_month` | 50.5 | 50.5 | 12 | 1200 | ok | Consultation |
| `consultations_by_sexe` | 151.1 | 151.8 | 2 | 1500 | ok | Consultation, Patient |
| `top_diagnostics` | 140.2 | 149.6 | 10 | 2000 | ok | Consultation, Diagnostic |
| `consultations_per_specialite` | 378.7 | 379.9 | 20 | 2500 | ok | Consultation, Professionnel_de_sante, Specialites |
| `top_medicaments_prescrits` | 98.2 | 99.0 | 20 | 2500 | ok | Medicaments, Prescription |
| `patients_with_many_consultations` | 260.4 | 263.6 | 50 | 2500 | ok | Consultation |
| `consultations_by_mutuelle` | 64.1 | 64.2 | 20 | 2000 | ok | Consultation, Mutuelle |
| `consultation_duration_by_weekday` | 386.4 | 388.4 | 7 | 1500 | ok | Consultation |
| `patient_by_num_secu` | 9.11 | 9.61 | 1 | 800 | ok | Patient |
| `consultations_of_one_patient` | 29.7 | 30.1 | 6 | 800 | ok | Consultation |
| `prescriptions_of_one_consultation` | 24.7 | 26.2 | 5 | 800 | ok | Prescription |
| `medicament_search` | 12.1 | 12.3 | 30 | 1200 | ok | Medicaments |

## Compared to the stored baseline

The query catalogue changed since the baseline was recorded, so the comparison is skipped. Update the baseline to start tracking the new queries.

## Acceptance criteria

| Criterion | Threshold | Measured | Verdict |
| --- | --- | --- | --- |
| Latency budget | 2.5x baseline, floor 100 ms | 12/12 within budget | PASS |
| Non-empty results | >= 1 row per query | 12/12 | PASS |
| Database size | <= 400 MB | 369 MB | PASS |
| Dump size | <= 50 MB | 47 MB | PASS |

Overall: **PASS**

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
