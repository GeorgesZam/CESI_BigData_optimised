#!/usr/bin/env python3
"""Copy the silver and gold layers from PostgreSQL into a DuckDB file.

The copy uses DuckDB's postgres extension and runs once, before the measurement.
The query timings never include this load.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb

TABLES = {
    "silver": [
        "patient",
        "consultation",
        "prescription",
        "medicament",
        "diagnostic",
        "mutuelle",
        "specialite",
        "professionnel",
        "laboratoire",
        "adher",
        "salle",
    ],
    "gold": [
        "dim_date",
        "dim_patient",
        "dim_professionnel",
        "dim_specialite",
        "dim_diagnostic",
        "dim_medicament",
        "dim_mutuelle",
        "fact_consultation",
        "fact_prescription",
        "mart_consultations_per_month",
        "mart_consultations_by_sexe",
        "mart_top_diagnostics",
        "mart_consultations_per_specialite",
        "mart_top_medicaments",
        "mart_patients_with_many",
        "mart_consultations_by_mutuelle",
        "mart_duration_by_weekday",
    ],
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", required=True, help="libpq connection string")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    if args.out.exists():
        args.out.unlink()
    args.out.parent.mkdir(parents=True, exist_ok=True)

    connection = duckdb.connect(str(args.out))
    connection.execute("INSTALL postgres")
    connection.execute("LOAD postgres")
    connection.execute(f"ATTACH '{args.dsn}' AS pg (TYPE postgres, READ_ONLY)")
    for schema, tables in TABLES.items():
        connection.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        for table in tables:
            connection.execute(
                f"CREATE OR REPLACE TABLE {schema}.{table} AS "
                f"SELECT * FROM pg.{schema}.{table}"
            )
    connection.execute("DETACH pg")
    rows = connection.execute("SELECT count(*) FROM gold.fact_consultation").fetchone()[0]
    marts = connection.execute("SELECT count(*) FROM gold.mart_consultations_per_month").fetchone()[0]
    connection.close()
    print(f"{args.out} written, {rows} consultations, {marts} months")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
