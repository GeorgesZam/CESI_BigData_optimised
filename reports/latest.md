# Database performance report

- Generated: 2026-11-02 14:22:50 UTC
- Database: PostgreSQL 14.24 (Debian 14.24-1.pgdg13+2) on x86_64-pc-linux-gnu, compiled by gcc (Debian 14.2.0-19) 14.2.0, 64-bit
- Size: 1175 MB, ~10,436,232 rows
- Host: 4 vCPU, 15.6 GiB RAM, 82.8 GiB free disk of 144.3 GiB
- Runner: Linux 7.0.0-1017-azure / Python 3.12.15
- Method: 1 warm-up run(s), 3 measured run(s), median and p95 wall time

## Measurements (database as restored, no modification)

Budgets are 2.5x the stored baseline median, rounded up to 50 ms with a floor of 100 ms. The SQL budget applies when no baseline exists.

| Query | Median (ms) | p95 (ms) | Rows | Budget (ms) | Status | Seq scans |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| `consultations_per_month` | 0.09 | 0.11 | 12 | 1200 | ok | mart_consultations_per_month |
| `consultations_by_sexe` | 0.07 | 0.09 | 2 | 1500 | ok | mart_consultations_by_sexe |
| `top_diagnostics` | 0.65 | 0.67 | 10 | 2000 | ok | mart_top_diagnostics |
| `consultations_per_specialite` | 0.09 | 0.09 | 20 | 2500 | ok | mart_consultations_per_specialite |
| `top_medicaments_prescrits` | 0.62 | 0.62 | 20 | 2500 | ok | mart_top_medicaments |
| `patients_with_many_consultations` | 0.31 | 0.32 | 50 | 2500 | ok | mart_patients_with_many |
| `consultations_by_mutuelle` | 0.08 | 0.08 | 20 | 2000 | ok | mart_consultations_by_mutuelle |
| `consultation_duration_by_weekday` | 0.08 | 0.10 | 7 | 1500 | ok | mart_duration_by_weekday |
| `patient_by_num_secu` | 0.08 | 0.09 | 1 | 800 | ok | none |
| `consultations_of_one_patient` | 0.09 | 0.12 | 6 | 800 | ok | none |
| `prescriptions_of_one_consultation` | 0.15 | 0.18 | 5 | 800 | ok | none |
| `medicament_search` | 0.23 | 0.26 | 30 | 1200 | ok | none |
| `fact_consultations_per_year` | 4.36 | 4.57 | 1 | 1500 | ok | fact_consultation_2022_b0, fact_consultation_2022_b1, fact_consultation_2022_b2, fact_consultation_2022_b3, fact_consultation_2022_b4, fact_consultation_2022_b5, fact_consultation_2022_b6, fact_consultation_2022_b7 |
| `fact_consultations_of_patient` | 4.22 | 4.44 | 1 | 1500 | ok | fact_consultation_2015_b1, fact_consultation_2016_b1, fact_consultation_2017_b1, fact_consultation_2018_b1, fact_consultation_2019_b1, fact_consultation_2020_b1, fact_consultation_2021_b1, fact_consultation_2022_b1, fact_consultation_2023_b1, fact_consultation_default_b1 |

## Compared to the stored baseline

The query catalogue changed since the baseline was recorded, so the comparison is skipped. Update the baseline to start tracking the new queries.

## Acceptance criteria

| Criterion | Threshold | Measured | Verdict |
| --- | --- | --- | --- |
| Latency budget | 2.5x baseline, floor 100 ms | 14/14 within budget | PASS |
| Non-empty results | >= 1 row per query | 14/14 | PASS |
| Database size | <= 1600 MB | 1232 MB | PASS |
| Dump size | <= 50 MB | 47 MB | PASS |

Overall: **PASS**

## Resources

| Resource | Value |
| --- | --- |
| CPU | 4 vCPU |
| RAM | 15.6 GiB |
| Disk | 82.8 GiB free of 144.3 GiB |
| Database size | 1175 MB |
| Dump size | 47.0 MB |
| `shared_buffers` | 128MB |
| `work_mem` | 4MB |
| `effective_cache_size` | 4GB |
| `max_parallel_workers_per_gather` | 2 |

## Storage cost estimate

| Stored object | Size (decimal GB) | S3 Standard | S3 Standard-IA | S3 Glacier Deep Archive |
| --- | ---: | ---: | ---: | ---: |
| Database (restored) | 1.232 | $0.0283/mo | $0.0154/mo | $0.0012/mo |
| Dump file | 0.047 | $0.0011/mo | $0.0006/mo | $0.0000/mo |

Prices are us-east-1 list prices per GB-month for storage only. They exclude requests, egress, versioning and any other AWS service. Sizes use decimal GB (10^9 bytes), as AWS bills them.

## Notes

- Timings come from a shared GitHub runner: compare runs from the same job, not absolute values across jobs.
- Queries under about 1 ms are dominated by measurement noise; their ratios are not meaningful.
- `VACUUM (ANALYZE)` runs before the measurement so the planner has real statistics. It does not change data or indexes.
