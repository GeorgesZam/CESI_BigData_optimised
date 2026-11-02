#!/usr/bin/env python3
"""Build the bronze, silver and gold layers with psql.

Bronze is the restored dump. Silver is cleaned, typed and constrained. Gold is the
star schema and the business marts used by the benchmark queries.

Each SQL file is executed by psql with ON_ERROR_STOP, and the build time of each
layer is written to JSON and Markdown.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--sql-dir", type=Path, default=Path("sql"))
    parser.add_argument("--psql", default="psql")
    parser.add_argument("--json-out", type=Path, default=Path("bench/etl.json"))
    parser.add_argument("--md-out", type=Path, default=Path("bench/etl-report.md"))
    args = parser.parse_args()

    files = sorted(args.sql_dir.glob("*.sql"))
    if not files:
        raise SystemExit(f"no SQL file in {args.sql_dir}")

    layers = []
    for path in files:
        started = time.perf_counter()
        result = subprocess.run(
            [
                args.psql,
                args.dsn,
                "-X",
                "-v",
                "ON_ERROR_STOP=1",
                "-q",
                "-f",
                str(path),
            ],
            capture_output=True,
            text=True,
        )
        elapsed = time.perf_counter() - started
        if result.returncode != 0:
            print(result.stdout, file=sys.stderr)
            print(result.stderr, file=sys.stderr)
            raise SystemExit(f"{path.name} failed with exit code {result.returncode}")
        layers.append({"file": path.name, "seconds": round(elapsed, 2)})
        print(f"{path.name}: {elapsed:.1f}s", file=sys.stderr)

    total = round(sum(layer["seconds"] for layer in layers), 2)
    document = {"layers": layers, "total_seconds": total}
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    lines = ["# Medallion build", "", "| Step | Seconds |", "| --- | ---: |"]
    for layer in layers:
        lines.append(f"| `{layer['file']}` | {layer['seconds']:.1f} |")
    lines += ["", f"Total: **{total:.1f} s**", ""]
    args.md_out.parent.mkdir(parents=True, exist_ok=True)
    args.md_out.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
