# CESI_BigData_optimised

PostgreSQL performance project on a French healthcare dataset (2024 extract,
`DATA 2024/`). The repository ships a database dump and a GitHub Actions benchmark
that measures the database without modifying it.

## Objectives

The database is evaluated on three axes that pull against each other:

1. **Smaller data** — store the same information in as few bytes as possible:
   narrower column types, normalized dimensions, no duplicated columns.
2. **Faster queries** — keep the representative analytics and lookups fast on
   modest hardware, like a shared GitHub runner.
3. **More concurrent users** — serve as many parallel sessions as possible without
   saturating CPU, memory or I/O.

Every change is a trade-off. A smaller row layout reduces I/O but can slow some
queries. More indexes speed up reads but grow the database and add write cost. The
benchmark exists to measure those trade-offs instead of guessing.

What those axes mean for this dataset:

| Axis | Current situation | Typical levers |
| --- | --- | --- |
| Smaller data | 352 MB restored; wide `varchar` columns; dates stored as text; two scratch tables (`AAAA`, `date`) not referenced by any foreign key | real `date`/`integer` types, shorter keys, drop unused tables |
| Faster queries | only primary keys are indexed; joins on foreign keys and lookups on `Num_Secu` scan whole tables | indexes on join, date and search columns; fresh statistics; query rewrites |
| More concurrent users | each full scan holds CPU and shared buffers for its session | fewer scans, smaller rows, connection pooling, lower `work_mem` per session |

None of these levers is applied yet. The benchmark first records where the database
stands, so each later change can be judged on measured numbers.

## Dataset

- `DATA 2024/BDD PostgreSQL/DATA2023` — PostgreSQL 14 custom dump, 45 MB.
- 13 tables, about 3.7 million rows, 352 MB once restored.
- Fact tables: `Consultation` (1.03 M rows), `Prescription` (1.00 M),
  `Professionnel_de_sante` (1.05 M), `Salle` (0.20 M), `Patient` (0.10 M).
- The dump only contains primary keys and `NOT VALID` foreign keys: no index on
  join columns, dates or natural keys.
- The CSV/Excel/PDF files under `DATA 2024/` are the raw sources and are not needed
  by the benchmark.

## Benchmark

`.github/workflows/db-performance.yml` starts a PostgreSQL 14 service, restores the
dump, and runs `bench/benchmark.py`. The job:

- runs the 12 queries from the `queries/` folder: aggregations, multi-table joins,
  point lookups on unindexed keys, and a free-text search;
- reports median and p95 wall time, result row count, budget status, and the
  sequential scans chosen by the planner;
- compares the run to `bench/baseline.json`, so each iteration shows whether the
  database got faster or slower;
- reports runner resources (vCPU, RAM, disk), database and dump size, and a monthly
  Amazon S3 storage cost estimate;
- publishes the report in the Actions job summary and as an artifact.

The benchmark **does not optimize anything**: it creates no index, rewrites no query
and changes no data. It only measures the database as restored, plus a
`VACUUM (ANALYZE)` to give the planner real statistics.

## Repository layout

```
.github/workflows/db-performance.yml   CI: restore, measure, publish the report
queries/                               one SQL file per measured query
bench/benchmark.py                     measurement script
bench/baseline.json                    reference timings (created by the first manual run)
bench/README.md                        usage and methodology
reports/latest.md                      report committed with each new baseline
DATA 2024/                             source data and PostgreSQL dump
```

## Running the benchmark

See [`bench/README.md`](bench/README.md). Short version:

```bash
createdb cesi
pg_restore --no-owner --no-privileges -d cesi "DATA 2024/BDD PostgreSQL/DATA2023"

uv run --with "psycopg[binary]" python bench/benchmark.py \
  --dsn "postgresql://localhost:5432/cesi" \
  --repeats 5
```

## Tracking progress

1. Run the workflow manually once with `update_baseline = true` to record the
   reference on GitHub runners.
2. Every later run compares against that reference and marks each query as
   `faster`, `stable` or `slower`.
3. When a change is a real improvement, run again with `update_baseline = true`.
   The commit updates `bench/baseline.json` and `reports/latest.md`, so the history
   of each step stays in Git.

The current benchmark measures latency and data size one query at a time. A parallel
load test is the next step to measure throughput for many concurrent users.
