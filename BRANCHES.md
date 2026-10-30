# Branches

- `main` — industry standard stack: PostgreSQL, Python latency harness, Python
  concurrency stress test. Spark ETL for the bronze/silver/gold layers is planned.
- `optimized` — Rust harness (`tokio-postgres`) for the same queries and data. The
  DuckDB engine is the next step on this branch.

Both branches use the same `queries/` catalogue and the same dump, so their numbers
stay comparable. The workflow runs on manual dispatch only, to avoid spending
Actions minutes on every commit.
