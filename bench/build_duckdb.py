#!/usr/bin/env python3
"""Copy the PostgreSQL tables into a DuckDB file.

The copy uses DuckDB's postgres extension and runs once, before the measurement.
The query timings never include this load.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb

TABLES = [
    "AAAA",
    "Adher",
    "Consultation",
    "Diagnostic",
    "Laboratoire",
    "Medicaments",
    "Mutuelle",
    "Patient",
    "Prescription",
    "Professionnel_de_sante",
    "Salle",
    "Specialites",
    "date",
]


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
    connection.execute("CREATE SCHEMA IF NOT EXISTS public")
    for table in TABLES:
        connection.execute(
            f'CREATE OR REPLACE TABLE public."{table}" AS '
            f'SELECT * FROM pg.public."{table}"'
        )
    connection.execute("DETACH pg")
    rows = connection.execute('SELECT count(*) FROM public."Consultation"').fetchone()[0]
    connection.close()
    print(f"{args.out} written, {rows} consultations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
