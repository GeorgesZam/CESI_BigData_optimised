# Rust harness

`cesi-bench` measures the same queries as the Python harness, using
`tokio-postgres`. It reads `queries/`, runs one warm-up and three measured passes,
and writes JSON with median, p95, min and max per query.

## Build

```bash
cd rust
cargo build --release
```

## Run

```bash
./target/release/cesi-bench \
  --dsn "postgresql://postgres@localhost:5432/cesi" \
  --queries ../queries \
  --repeats 3 \
  --out rust/results.json
```

Options: `--dsn`, `--queries`, `--repeats`, `--warmup`, `--out`.

## Status

- PostgreSQL engine: working.
- DuckDB engine: next step. The same queries will run against Parquet exports of the
  PostgreSQL tables, so both engines see the same rows.
