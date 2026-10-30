# Branches

- `main` — PostgreSQL 14. Python harness, max-users stress test. No Spark, no Polars:
  they are data transformation tools, not serving engines.
- `optimized` — DuckDB. Same queries, same workload, same max-users test. The DuckDB
  file is built from the PostgreSQL dump once, before the measurement. The Rust
  harness in `rust/` measures the same queries against PostgreSQL; the DuckDB Rust
  engine is the next step.

Both branches write to the same single page: `gh-pages/index.html`, with one point per
run, the maximum number of users, and the blocking reason (CPU, memory, response time
or errors). The workflow runs on manual dispatch only, to avoid spending Actions
minutes on every commit.

## What a user does

One user sends one request per second (60 requests per minute), drawing from a fixed
weighted mix of the queries. The ramp runs 1, 2, 4, 8, 16, 32 and 64 users, 20 seconds
per level. It stops at the first failure: server unreachable, CPU at 90%, memory at
90%, error rate above 1%, p95 above 500 ms or p99 above 1000 ms.
