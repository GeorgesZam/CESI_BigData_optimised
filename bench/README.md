# Database performance benchmark

This folder contains a PostgreSQL benchmark. It measures the database as restored
from the dump, **without creating an index or changing any data**, and compares the
result to a stored reference so progress can be tracked across iterations.

- `../queries/` — one `.sql` file per query, with its purpose and time budget.
- `benchmark.py` — runs the queries, records median and p95, compares against
  `baseline.json`, and writes `report.md` and `results.json`.
- `baseline.json` — reference timings measured on GitHub Actions. Created by the
  first manual run (see below).

## GitHub Actions workflow

`.github/workflows/db-performance.yml` starts a PostgreSQL 14 service, restores the
dump, runs the benchmark, and publishes the report in the job summary
(**Actions** → run → **Summary**) and as an artifact.

Two ways to provide the dump:

1. **In the repository** — commit `DATA 2024/BDD PostgreSQL/DATA2023` (45 MB, below
   the 100 MB per-file GitHub limit).
2. **From a release** — upload the dump as a release asset, then set the `DUMP_URL`
   repository variable (Settings → Secrets and variables → Actions → Variables) to
   the asset URL. Recommended to keep the Git history small.

## How the database is started

In CI, the workflow declares a service container:

```yaml
services:
  postgres:
    image: postgres:14
    env:
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: cesi
    ports:
      - 5432:5432
    options: >-
      --health-cmd "pg_isready -U postgres -d cesi"
```

The job waits for the health check, then restores the dump with
`pg_restore --no-owner --no-privileges --exit-on-error`. Nothing else touches the
database: no `CREATE INDEX`, no data change.

Locally, any PostgreSQL 14 instance works. With Docker:

```bash
docker run --name cesi-pg -d \
  -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=cesi \
  -p 5432:5432 postgres:14

pg_restore -h localhost -U postgres -d cesi --no-owner --no-privileges \
  "DATA 2024/BDD PostgreSQL/DATA2023"
```

With Postgres.app, start the server, then `createdb cesi` and run the same
`pg_restore` command.

## What the report contains

- **Measurements** — median and p95 wall time per query, result rows, budget status,
  and the sequential scans chosen by the planner.
- **Compared to the stored baseline** — reference time, current time, change and a
  verdict (`faster`, `stable`, `slower`).
- **Resources** — runner vCPU, RAM, free disk, database size, dump size and the main
  PostgreSQL settings.
- **Storage cost estimate** — monthly cost of the database and the dump on Amazon S3,
  at us-east-1 list prices (Standard, Standard-IA, Glacier Deep Archive), storage
  only. Prices are constants in `benchmark.py` and must be checked when AWS changes
  them.

## Tracking progress

1. First manual run: **Actions → Database performance → Run workflow** with
   `update_baseline = true`. The job measures the database, commits
   `bench/baseline.json` and copies the report to `reports/latest.md`.
2. Every later run (push, pull request or manual) prints a
   "Compared to the stored baseline" table.
3. When a change is a real improvement, run again with `update_baseline = true` to
   commit the new reference. `git log -p bench/baseline.json` keeps the history of
   each step.

The job fails on a budget overrun or a regression only with `enforce_budget = true`.
A regression is reported beyond 25% and 2 ms of difference, to ignore the noise of a
shared runner.

## Running locally

```bash
createdb cesi
pg_restore --no-owner --no-privileges -d cesi "DATA 2024/BDD PostgreSQL/DATA2023"

uv run --with "psycopg[binary]" python bench/benchmark.py \
  --dsn "postgresql://localhost:5432/cesi" \
  --dump "DATA 2024/BDD PostgreSQL/DATA2023" \
  --repeats 5
```

Useful options: `--baseline bench/baseline.json` to compare,
`--write-baseline bench/baseline.json` to record a reference, `--strict` to fail on a
budget overrun or a regression.

## Method and limits

- `VACUUM (ANALYZE)` runs before the measurement so the planner has real statistics
  (the dump contains none). It changes neither data nor indexes.
- Each query gets one warm-up run and 5 measured runs; the report shows median and
  p95.
- Absolute timings on a shared GitHub runner vary: compare queries within one run,
  and trust the change against the reference more than the raw values.
- Queries under about 1 ms are dominated by measurement noise.
- The benchmark measures latency and database size, not concurrent throughput.
