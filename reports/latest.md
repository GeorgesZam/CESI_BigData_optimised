# Database performance report

- Generated: 2026-11-02 14:14:56 UTC
- Database: PostgreSQL 14.24 (Debian 14.24-1.pgdg13+2) on x86_64-pc-linux-gnu, compiled by gcc (Debian 14.2.0-19) 14.2.0, 64-bit
- Size: 1230 MB, ~10,436,232 rows
- Host: 4 vCPU, 15.6 GiB RAM, 82.8 GiB free disk of 144.3 GiB
- Runner: Linux 7.0.0-1017-azure / Python 3.12.15
- Method: 1 warm-up run(s), 3 measured run(s), median and p95 wall time

## Measurements (database as restored, no modification)

Budgets are 2.5x the stored baseline median, rounded up to 50 ms with a floor of 100 ms. The SQL budget applies when no baseline exists.

| Query | Median (ms) | p95 (ms) | Rows | Budget (ms) | Status | Seq scans |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| `consultations_per_month` | 0.26 | 0.30 | 12 | 1200 | ok | mart_consultations_per_month |
| `consultations_by_sexe` | 0.24 | 0.24 | 2 | 1500 | ok | mart_consultations_by_sexe |
| `top_diagnostics` | 1.41 | 1.41 | 10 | 2000 | ok | mart_top_diagnostics |
| `consultations_per_specialite` | 0.23 | 0.24 | 20 | 2500 | ok | mart_consultations_per_specialite |
| `top_medicaments_prescrits` | 1.35 | 1.37 | 20 | 2500 | ok | mart_top_medicaments |
| `patients_with_many_consultations` | 0.69 | 0.69 | 50 | 2500 | ok | mart_patients_with_many |
| `consultations_by_mutuelle` | 0.24 | 0.28 | 20 | 2000 | ok | mart_consultations_by_mutuelle |
| `consultation_duration_by_weekday` | 0.23 | 0.24 | 7 | 1500 | ok | mart_duration_by_weekday |
| `patient_by_num_secu` | 0.23 | 0.25 | 1 | 800 | ok | none |
| `consultations_of_one_patient` | 0.27 | 0.30 | 6 | 800 | ok | none |
| `prescriptions_of_one_consultation` | 0.35 | 0.41 | 5 | 800 | ok | none |
| `medicament_search` | 0.55 | 0.57 | 30 | 1200 | ok | none |
| `fact_consultations_per_year` | 8.88 | 9.05 | 1 | 1500 | ok | fact_consultation_2022 |

## Compared to the stored baseline

The query catalogue changed since the baseline was recorded, so the comparison is skipped. Update the baseline to start tracking the new queries.

## Acceptance criteria

| Criterion | Threshold | Measured | Verdict |
| --- | --- | --- | --- |
| Latency budget | 2.5x baseline, floor 100 ms | 13/13 within budget | PASS |
| Non-empty results | >= 1 row per query | 13/13 | PASS |
| Database size | <= 1600 MB | 1289 MB | PASS |
| Dump size | <= 50 MB | 47 MB | PASS |

Overall: **PASS**

## Resources

| Resource | Value |
| --- | --- |
| CPU | 4 vCPU |
| RAM | 15.6 GiB |
| Disk | 82.8 GiB free of 144.3 GiB |
| Database size | 1230 MB |
| Dump size | 47.0 MB |
| `shared_buffers` | 128MB |
| `work_mem` | 4MB |
| `effective_cache_size` | 4GB |
| `max_parallel_workers_per_gather` | 2 |

## Storage cost estimate

| Stored object | Size (decimal GB) | S3 Standard | S3 Standard-IA | S3 Glacier Deep Archive |
| --- | ---: | ---: | ---: | ---: |
| Database (restored) | 1.289 | $0.0297/mo | $0.0161/mo | $0.0013/mo |
| Dump file | 0.047 | $0.0011/mo | $0.0006/mo | $0.0000/mo |

Prices are us-east-1 list prices per GB-month for storage only. They exclude requests, egress, versioning and any other AWS service. Sizes use decimal GB (10^9 bytes), as AWS bills them.

## Notes

- Timings come from a shared GitHub runner: compare runs from the same job, not absolute values across jobs.
- Queries under about 1 ms are dominated by measurement noise; their ratios are not meaningful.
- `VACUUM (ANALYZE)` runs before the measurement so the planner has real statistics. It does not change data or indexes.
