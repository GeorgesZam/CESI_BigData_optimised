# Database performance benchmark

Two measurements run on every push, in separate jobs:

- **Latency benchmark** — the 12 queries from `../queries/`, one at a time, median
  and p95.
- **Concurrency stress test** — a weighted query mix with a growing number of
  clients, until the database fails or leaves the SLA.

Neither job creates an index, rewrites a query or changes data. The database is only
restored and measured.

## Files

- `../queries/` — one `.sql` file per measured query, with its budget.
- `benchmark.py` — latency measurement, acceptance criteria, report and baseline.
- `stress.py` — concurrency ramp, failure detection, stress report.
- `thresholds.json` — acceptance criteria and stress settings.
- `baseline.json` — reference timings recorded on GitHub Actions.
- `requirements.txt` — Python dependency (`psycopg`).

## GitHub Actions

`.github/workflows/db-performance.yml` runs two jobs:

1. `benchmark` — PostgreSQL 14 service, restore, latency measurement, report.
2. `stress` — a second PostgreSQL 14 service capped at 2 GB of memory, restore,
   concurrency ramp.

Both publish a report in the job summary (**Actions** → run → **Summary**) and as
artifacts. The latency job also commits `bench/baseline.json` and
`reports/latest.md` when run manually with `update_baseline = true`.

Two ways to provide the dump:

1. **In the repository** — commit `DATA 2024/BDD PostgreSQL/DATA2023` (45 MB).
2. **From a release** — upload the dump as a release asset and set the `DUMP_URL`
   repository variable. Recommended to keep the Git history small.

## How the database is started

In CI, each job declares its own service container:

```yaml
services:
  postgres:
    image: postgres:14
    env:
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: cesi
    options: >-
      --health-cmd "pg_isready -U postgres -d cesi"
```

The stress job adds `--memory=2g --memory-swap=2g`, so memory exhaustion is a
possible failure mode. The dump is restored with
`pg_restore -j 4 --no-owner --no-privileges --exit-on-error`.

Locally, any PostgreSQL 14 instance works. With Docker:

```bash
docker run --name cesi-pg -d \
  -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=cesi \
  -p 5432:5432 postgres:14

pg_restore -h localhost -U postgres -d cesi --no-owner --no-privileges \
  "DATA 2024/BDD PostgreSQL/DATA2023"
```

## Acceptance criteria

`thresholds.json` holds the criteria. The latency report prints a PASS/FAIL table:

| Criterion | Threshold |
| --- | --- |
| Latency budget | 2.5x the baseline median, rounded to 50 ms, floor 100 ms |
| Regression vs baseline | at most +15% and +1 ms |
| Non-empty results | at least one row per query |
| Database size | at most 400 MB |
| Dump size | at most 50 MB |

Budgets come from the stored baseline, so they tighten as the database improves. The
SQL `-- budget_ms` line is only a fallback when no baseline exists. `--strict` makes
the job fail on any FAIL; without it the job reports and stays green.

## Stress test

The stress job ramps 1, 4, 8, 16, 32 and 64 concurrent clients, 15 seconds per
level after a 5-second warm-up. Each client runs a weighted mix of the queries from a
fixed deck, so the mix is identical from one run to the next:

| Query | Weight |
| --- | ---: |
| `patient_by_num_secu` | 35 |
| `consultations_of_one_patient` | 20 |
| `prescriptions_of_one_consultation` | 15 |
| `medicament_search` | 15 |
| `consultations_per_month` | 8 |
| `top_diagnostics` | 4 |
| `consultations_by_sexe` | 2 |
| `consultations_per_specialite` | 1 |

The ramp stops at the first failure:

- the server no longer answers (crash, OOM kill, refused connection);
- the error rate exceeds 1%;
- p95 exceeds 500 ms or p99 exceeds 1000 ms;
- or every level passed.

The report shows transactions, throughput, p50/p95/p99/max, errors and the breaking
point. The test passes when at least 8 clients stay within the SLA (`min_clients`).
`--strict` makes the job fail when it does not.

The client runs on the same 4 vCPU machine as PostgreSQL, so at high concurrency the
load generator competes with the database for CPU. The breaking point is a lower
bound.

## Graphs

`github-action-benchmark` pushes history to the `gh-pages` branch and renders charts:

- `dev/bench/latency/` — total and per-query median over commits.
- `dev/bench/stress-latency/` — p95, p99 and error rate at 8 clients.
- `dev/bench/stress-throughput/` — throughput at 8 clients and max clients within SLA.

Enable GitHub Pages once (Settings → Pages → branch `gh-pages`, folder `/`). The
charts then live at `https://<owner>.github.io/<repo>/dev/bench/latency/` and the two
other paths.

## Tracking progress

1. First manual run: **Actions → Database performance → Run workflow** with
   `update_baseline = true`. The job commits `bench/baseline.json` and
   `reports/latest.md`.
2. Every later run compares against that reference and marks each query
   `faster`, `stable` or `slower`.
3. When a change is a real improvement, run again with `update_baseline = true`.
   `git log -p bench/baseline.json` keeps the history of each step.

## Running locally

```bash
createdb cesi
pg_restore -h localhost -U postgres -d cesi --no-owner --no-privileges \
  "DATA 2024/BDD PostgreSQL/DATA2023"

uv run --with "psycopg[binary]" python bench/benchmark.py \
  --dsn "postgresql://localhost:5432/cesi" \
  --dump "DATA 2024/BDD PostgreSQL/DATA2023" \
  --repeats 3

uv run --with "psycopg[binary]" python bench/stress.py \
  --dsn "postgresql://localhost:5432/cesi"
```

Options: `--baseline bench/baseline.json` to compare, `--write-baseline` to record a
reference, `--strict` to fail on a criterion. For a short local stress run, edit the
`stress.clients` and `stress.duration_seconds` values in a copy of
`thresholds.json`.

## Method and limits

- `VACUUM (ANALYZE)` runs before the latency measurement so the planner has real
  statistics. It changes neither data nor indexes.
- Each query gets one warm-up run and 3 measured runs in CI; the report shows median
  and p95.
- Absolute timings on a shared runner vary: compare queries within one run, and trust
  the change against the reference more than the raw values.
- Queries under about 1 ms are dominated by measurement noise.
