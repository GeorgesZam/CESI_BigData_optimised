#!/usr/bin/env python3
"""Benchmark the CESI healthcare PostgreSQL database.

Restores are expected to be done beforehand (see .github/workflows/db-performance.yml).
The script only measures the database as restored: it creates no index and changes
no data.

1. loads the queries from the queries/ folder, one file per query,
2. runs each query after a warm-up round and records median / p95 wall time,
3. optionally compares the run to a stored baseline (bench/baseline.json),
4. writes a Markdown report and a JSON file with timings, resources and a storage
   cost estimate.

Without --strict the script always exits 0: it is a report. With --strict it
exits 1 when a query exceeds its budget or regresses against the baseline.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import re
import shutil
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import psycopg

SERVER_SETTINGS = (
    "shared_buffers",
    "work_mem",
    "effective_cache_size",
    "max_parallel_workers_per_gather",
)

# S3 list prices in us-east-1, USD per GB-month, storage only. They exclude
# requests, egress and versioning. Update them when AWS changes its price list.
S3_PRICES = {
    "S3 Standard": 0.023,
    "S3 Standard-IA": 0.0125,
    "S3 Glacier Deep Archive": 0.00099,
}


def load_queries(folder: Path) -> list[dict]:
    if not folder.is_dir():
        raise SystemExit(f"{folder} is not a directory")
    files = sorted(folder.glob("*.sql"))
    if not files:
        raise SystemExit(f"no query found in {folder}")

    queries = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        budget = re.search(r"(?m)^--\s*budget_ms:\s*(\d+)\s*$", text)
        sql = "\n".join(
            line for line in text.splitlines() if not line.strip().startswith("--")
        ).strip()
        if not sql.endswith(";"):
            raise SystemExit(f"query {path.name} does not end with a semicolon")
        queries.append(
            {
                "name": re.sub(r"^\d+[_-]", "", path.stem),
                "budget_ms": int(budget.group(1)) if budget else None,
                "sql": sql.rstrip(";"),
                "file": path.name,
            }
        )
    return queries


def queries_fingerprint(folder: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(folder.glob("*.sql")):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * fraction
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def plan_nodes(plan: dict):
    yield plan
    for child in plan.get("Plans", []):
        yield from plan_nodes(child)


def host_facts() -> dict:
    try:
        memory_bytes = os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
    except (ValueError, OSError, AttributeError):
        memory_bytes = None
    disk = shutil.disk_usage("/")
    return {
        "cpus": os.cpu_count(),
        "memory_bytes": memory_bytes,
        "disk_total_bytes": disk.total,
        "disk_free_bytes": disk.free,
    }


def db_facts(conn) -> dict:
    version = conn.execute("select version()").fetchone()[0]
    size_bytes = conn.execute("select pg_database_size(current_database())").fetchone()[0]
    size = conn.execute("select pg_size_pretty(pg_database_size(current_database()))").fetchone()[0]
    rows = conn.execute(
        "select coalesce(sum(n_live_tup), 0) from pg_stat_user_tables"
    ).fetchone()[0]
    settings = {name: conn.execute(f"show {name}").fetchone()[0] for name in SERVER_SETTINGS}
    return {
        "version": version,
        "database_size": size,
        "database_size_bytes": int(size_bytes),
        "estimated_rows": int(rows),
        "settings": settings,
    }


def measure(conn, queries: list[dict], repeats: int, warmup: int) -> list[dict]:
    results = []
    for query in queries:
        for _ in range(warmup):
            conn.execute(query["sql"]).fetchall()

        timings = []
        row_count = 0
        for _ in range(repeats):
            started = time.perf_counter()
            row_count = len(conn.execute(query["sql"]).fetchall())
            timings.append((time.perf_counter() - started) * 1000.0)

        plan = conn.execute(
            "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + query["sql"]
        ).fetchone()[0][0]
        plan_time = plan.get("Execution Time", 0.0)
        top_node = plan["Plan"]["Node Type"]
        seq_scans = [
            node.get("Relation Name", "?")
            for node in plan_nodes(plan["Plan"])
            if node.get("Node Type") == "Seq Scan"
        ]

        results.append(
            {
                "name": query["name"],
                "file": query["file"],
                "median_ms": round(statistics.median(timings), 2),
                "p95_ms": round(percentile(timings, 0.95), 2),
                "min_ms": round(min(timings), 2),
                "max_ms": round(max(timings), 2),
                "rows": row_count,
                "budget_ms": query["budget_ms"],
                "plan_exec_ms": round(plan_time, 2),
                "plan_top_node": top_node,
                "plan_seq_scans": sorted(set(seq_scans)),
                "plan_shared_hit_blocks": plan["Plan"].get("Shared Hit Blocks", 0),
                "plan_shared_read_blocks": plan["Plan"].get("Shared Read Blocks", 0),
                "samples_ms": [round(value, 2) for value in timings],
            }
        )
    return results


def fmt_ms(value: float) -> str:
    return f"{value:.2f}" if value < 10 else f"{value:.1f}"


def fmt_gib(value: int | None) -> str:
    return "unknown" if value is None else f"{value / 2**30:.1f} GiB"


def fmt_size(value: int | None) -> str:
    if value is None:
        return "unknown"
    for unit in ("B", "kB", "MB", "GB"):
        if value < 1000 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1000
    return f"{value:.1f} GB"


def status_for(row: dict) -> str:
    if row["budget_ms"] is None:
        return "no budget"
    return "ok" if row["median_ms"] <= row["budget_ms"] else "over budget"


def compare_to_baseline(
    current: list[dict], document: dict, tolerance: float, noise_floor_ms: float
) -> dict:
    stored = document.get("queries", {})
    rows = []
    for row in current:
        previous = stored.get(row["name"])
        if previous is None:
            continue
        old = previous["median_ms"]
        new = row["median_ms"]
        difference = new - old
        if old < 0.5:
            verdict = "noise"
        elif difference > noise_floor_ms and new > old * (1 + tolerance):
            verdict = "slower"
        elif difference < -noise_floor_ms and new < old * (1 - tolerance):
            verdict = "faster"
        else:
            verdict = "stable"
        rows.append(
            {
                "name": row["name"],
                "baseline_ms": old,
                "current_ms": new,
                "change_pct": round((difference / old * 100.0) if old else 0.0, 1),
                "verdict": verdict,
            }
        )

    comparable = [row for row in rows if row["baseline_ms"] >= 0.5 and row["current_ms"] > 0]
    speedups = [row["baseline_ms"] / row["current_ms"] for row in comparable]
    geomean = math.exp(sum(math.log(value) for value in speedups) / len(speedups)) if speedups else None
    total_old = sum(row["baseline_ms"] for row in rows)
    total_new = sum(row["current_ms"] for row in rows)

    return {
        "valid": True,
        "baseline": {
            "commit": document.get("commit"),
            "created_at": document.get("created_at"),
        },
        "rows": rows,
        "total_baseline_ms": round(total_old, 2),
        "total_current_ms": round(total_new, 2),
        "total_change_pct": round((total_new - total_old) / total_old * 100.0, 1) if total_old else 0.0,
        "geomean_speedup": round(geomean, 2) if geomean else None,
        "geomean_queries": len(comparable),
        "regressions": [row["name"] for row in rows if row["verdict"] == "slower"],
    }


def build_baseline_document(
    meta: dict, rows: list[dict], fingerprint: str, commit: str | None
) -> dict:
    return {
        "created_at": meta["generated_at"],
        "commit": commit,
        "queries_sha256": fingerprint,
        "queries": {
            row["name"]: {"median_ms": row["median_ms"], "p95_ms": row["p95_ms"]}
            for row in rows
        },
    }


def storage_cost_lines(meta: dict) -> list[str]:
    objects = [("Database (restored)", meta["db"]["database_size_bytes"])]
    dump = meta.get("dump") or {}
    if dump.get("size_bytes"):
        objects.append(("Dump file", dump["size_bytes"]))

    lines = [
        "| Stored object | Size (decimal GB) | " + " | ".join(S3_PRICES) + " |",
        "| --- | ---: | " + " | ".join("---:" for _ in S3_PRICES) + " |",
    ]
    for label, size_bytes in objects:
        gigabytes = size_bytes / 1e9
        costs = " | ".join(f"${gigabytes * price:,.4f}/mo" for price in S3_PRICES.values())
        lines.append(f"| {label} | {gigabytes:.3f} | {costs} |")
    lines += [
        "",
        "Prices are us-east-1 list prices per GB-month for storage only. They exclude "
        "requests, egress, versioning and any other AWS service. Sizes use decimal GB "
        "(10^9 bytes), as AWS bills them.",
    ]
    return lines


def render_report(
    meta: dict,
    results: list[dict],
    comparison: dict | None,
    baseline_status: str,
) -> str:
    host = meta["host"]
    settings = meta["db"]["settings"]
    lines = ["# Database performance report", ""]
    lines.append(f"- Generated: {meta['generated_at']}")
    lines.append(f"- Database: {meta['db']['version']}")
    lines.append(f"- Size: {meta['db']['database_size']}, ~{meta['db']['estimated_rows']:,} rows")
    lines.append(
        f"- Host: {host['cpus']} vCPU, {fmt_gib(host['memory_bytes'])} RAM, "
        f"{fmt_gib(host['disk_free_bytes'])} free disk of {fmt_gib(host['disk_total_bytes'])}"
    )
    lines.append(f"- Runner: {meta['platform']}")
    lines.append(
        f"- Method: {meta['warmup']} warm-up run(s), {meta['repeats']} measured run(s), "
        "median and p95 wall time"
    )
    lines.append("")

    lines.append("## Measurements (database as restored, no modification)")
    lines.append("")
    lines.append("| Query | Median (ms) | p95 (ms) | Rows | Budget (ms) | Status | Seq scans |")
    lines.append("| --- | ---: | ---: | ---: | ---: | --- | --- |")
    for row in results:
        budget = row["budget_ms"] if row["budget_ms"] is not None else "-"
        seq = ", ".join(row["plan_seq_scans"]) if row["plan_seq_scans"] else "none"
        lines.append(
            f"| `{row['name']}` | {fmt_ms(row['median_ms'])} | {fmt_ms(row['p95_ms'])} | {row['rows']} | "
            f"{budget} | {status_for(row)} | {seq} |"
        )
    lines.append("")

    lines += ["## Compared to the stored baseline", ""]
    if baseline_status == "missing":
        lines += ["No `bench/baseline.json` yet. Run the workflow manually with "
                  "`update_baseline = true` to record one.", ""]
    elif baseline_status == "changed":
        lines += ["The query catalogue changed since the baseline was recorded, so the comparison "
                  "is skipped. Update the baseline to start tracking the new queries.", ""]
    elif comparison is not None:
        info = comparison["baseline"]
        commit = (info["commit"] or "unknown")[:8]
        lines += [f"Baseline: recorded {info['created_at']} at commit `{commit}`.",
                  "", "| Query | Baseline (ms) | Current (ms) | Change | Verdict |",
                  "| --- | ---: | ---: | ---: | --- |"]
        for row in comparison["rows"]:
            lines.append(
                f"| `{row['name']}` | {fmt_ms(row['baseline_ms'])} | {fmt_ms(row['current_ms'])} | "
                f"{row['change_pct']:+.1f}% | {row['verdict']} |"
            )
        lines.append("")
        lines.append(
            f"Total of medians: {fmt_ms(comparison['total_baseline_ms'])} ms -> "
            f"{fmt_ms(comparison['total_current_ms'])} ms "
            f"({comparison['total_change_pct']:+.1f}%). "
            f"Geometric mean speed-up: {comparison['geomean_speedup']}x over "
            f"{comparison['geomean_queries']} queries >= 0.5 ms."
        )
        if comparison["regressions"]:
            lines.append("")
            lines.append("Regressions: " + ", ".join(f"`{name}`" for name in comparison["regressions"]))
        lines.append("")

    lines += ["## Resources", "",
              "| Resource | Value |", "| --- | --- |",
              f"| CPU | {host['cpus']} vCPU |",
              f"| RAM | {fmt_gib(host['memory_bytes'])} |",
              f"| Disk | {fmt_gib(host['disk_free_bytes'])} free of {fmt_gib(host['disk_total_bytes'])} |",
              f"| Database size | {meta['db']['database_size']} |",
              f"| Dump size | {fmt_size((meta.get('dump') or {}).get('size_bytes'))} |",
              f"| `shared_buffers` | {settings['shared_buffers']} |",
              f"| `work_mem` | {settings['work_mem']} |",
              f"| `effective_cache_size` | {settings['effective_cache_size']} |",
              f"| `max_parallel_workers_per_gather` | {settings['max_parallel_workers_per_gather']} |",
              ""]

    lines += ["## Storage cost estimate", ""]
    lines += storage_cost_lines(meta)
    lines.append("")

    lines += [
        "## Notes",
        "",
        "- Timings come from a shared GitHub runner: compare runs from the same job, not absolute values across jobs.",
        "- Queries under about 1 ms are dominated by measurement noise; their ratios are not meaningful.",
        "- `VACUUM (ANALYZE)` runs before the measurement so the planner has real statistics. "
        "It does not change data or indexes.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", default=os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/cesi"))
    parser.add_argument("--queries", type=Path, default=Path("queries"), help="folder with one .sql file per query")
    parser.add_argument("--dump", type=Path, default=None, help="dump file, only used to report its size")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--json-out", type=Path, default=Path("bench/results.json"))
    parser.add_argument("--report-out", type=Path, default=Path("bench/report.md"))
    parser.add_argument("--baseline", type=Path, default=None, help="stored baseline to compare against")
    parser.add_argument("--write-baseline", type=Path, default=None, help="record the current run as the new baseline")
    parser.add_argument("--commit", default=None, help="commit SHA stored in the baseline")
    parser.add_argument("--tolerance", type=float, default=0.25, help="relative change allowed before flagging a regression")
    parser.add_argument("--noise-floor-ms", type=float, default=2.0, help="absolute change below this is ignored")
    parser.add_argument("--strict", action="store_true", help="exit non-zero on a budget overrun or a regression")
    args = parser.parse_args()

    queries = load_queries(args.queries)
    fingerprint = queries_fingerprint(args.queries)
    dump_size = args.dump.stat().st_size if args.dump and args.dump.exists() else None
    meta: dict = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "platform": f"{platform.system()} {platform.release()} / Python {platform.python_version()}",
        "repeats": args.repeats,
        "warmup": args.warmup,
        "queries_folder": str(args.queries),
        "queries_sha256": fingerprint,
        "host": host_facts(),
        "dump": {"path": str(args.dump) if args.dump else None, "size_bytes": dump_size},
    }

    with psycopg.connect(args.dsn, autocommit=True) as conn:
        conn.execute("SET jit = off")
        conn.execute("SET statement_timeout = '180s'")
        maintenance_started = time.perf_counter()
        conn.execute("VACUUM (ANALYZE)")
        meta["maintenance_seconds"] = round(time.perf_counter() - maintenance_started, 2)
        meta["db"] = db_facts(conn)
        results = measure(conn, queries, args.repeats, args.warmup)

    baseline_status = "absent"
    comparison = None
    if args.baseline is not None:
        if not args.baseline.exists():
            baseline_status = "missing"
        else:
            document = json.loads(args.baseline.read_text(encoding="utf-8"))
            if document.get("queries_sha256") != fingerprint:
                baseline_status = "changed"
            else:
                baseline_status = "ok"
                comparison = compare_to_baseline(results, document, args.tolerance, args.noise_floor_ms)

    report = render_report(meta, results, comparison, baseline_status)
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.write_text(report, encoding="utf-8")
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(
            {"meta": meta, "results": results, "comparison": comparison},
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    if args.write_baseline is not None:
        document = build_baseline_document(meta, results, fingerprint, args.commit)
        args.write_baseline.parent.mkdir(parents=True, exist_ok=True)
        args.write_baseline.write_text(
            json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    print(report)
    print(f"report: {args.report_out}\njson:   {args.json_out}")
    if args.write_baseline is not None:
        print(f"baseline: {args.write_baseline}")

    over = [row for row in results if row["budget_ms"] and row["median_ms"] > row["budget_ms"]]
    regressions = comparison["regressions"] if comparison else []
    if args.strict and (over or regressions):
        if over:
            print("\nBudget exceeded:", ", ".join(row["name"] for row in over), file=sys.stderr)
        if regressions:
            print("Regressed against the baseline:", ", ".join(regressions), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
