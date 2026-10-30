#!/usr/bin/env python3
"""Max-users stress test for DuckDB.

One user sends one request per second, drawing from the same weighted deck as the
PostgreSQL test. Each user gets its own read-only DuckDB connection. The ramp stops
at the first level where CPU, memory, response time or errors leave the SLA.

The report format is shared with the PostgreSQL stress test, and the result is
appended to the same gh-pages history with engine "duckdb".
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import psutil

from benchmark import fmt_ms, load_queries, load_thresholds, percentile
from stress import REASONS, build_deck, render_markdown


class ResourceSampler(threading.Thread):
    def __init__(self, memory_limit_bytes: int):
        super().__init__(daemon=True)
        self.memory_limit_bytes = memory_limit_bytes
        self.cpu: list[float] = []
        self.memory: list[float] = []
        self._stop_event = threading.Event()
        self.process = psutil.Process()

    def run(self) -> None:
        psutil.cpu_percent(None)
        while not self._stop_event.is_set():
            self.cpu.append(psutil.cpu_percent(None))
            rss = self.process.memory_info().rss
            self.memory.append(rss / self.memory_limit_bytes * 100.0)
            self._stop_event.wait(0.5)

    def stop(self) -> None:
        self._stop_event.set()

    def summary(self) -> dict:
        return {
            "cpu_avg_pct": round(statistics.mean(self.cpu), 1) if self.cpu else None,
            "cpu_max_pct": round(max(self.cpu), 1) if self.cpu else None,
            "memory_max_pct": round(max(self.memory), 1) if self.memory else None,
        }


def worker(db, deck, offset, deadline, think_time, memory_limit, latencies, errors, lock):
    try:
        connection = duckdb.connect(db, read_only=True)
        connection.execute(f"SET memory_limit='{memory_limit}'")
    except Exception as exc:
        with lock:
            errors.append(f"connect:{type(exc).__name__}")
        return

    index = offset
    try:
        while time.perf_counter() < deadline:
            query = deck[index % len(deck)]
            index += 1
            started = time.perf_counter()
            try:
                connection.execute(query["sql"]).fetchall()
                with lock:
                    latencies.append((time.perf_counter() - started) * 1000.0)
            except duckdb.OutOfMemoryException:
                with lock:
                    errors.append("out_of_memory")
                return
            except Exception as exc:
                with lock:
                    errors.append(type(exc).__name__)
            remaining = deadline - time.perf_counter()
            if remaining > 0:
                time.sleep(min(think_time, remaining))
    finally:
        connection.close()


def run_level(db, deck, clients, duration, think_time, memory_limit, memory_limit_bytes) -> dict:
    latencies: list[float] = []
    errors: list[str] = []
    lock = threading.Lock()
    sampler = ResourceSampler(memory_limit_bytes)
    sampler.start()
    deadline = time.perf_counter() + duration
    threads = [
        threading.Thread(
            target=worker,
            args=(
                db,
                deck,
                (worker_id * 13) % len(deck),
                deadline,
                think_time,
                memory_limit,
                latencies,
                errors,
                lock,
            ),
        )
        for worker_id in range(clients)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    sampler.stop()
    sampler.join()

    total = len(latencies) + len(errors)
    error_rate = (len(errors) / total * 100.0) if total else 0.0
    return {
        "clients": clients,
        "transactions": len(latencies),
        "errors": len(errors),
        "error_rate_pct": round(error_rate, 2),
        "throughput": round(len(latencies) / duration, 1),
        "p50_ms": round(percentile(latencies, 0.50), 1) if latencies else None,
        "p95_ms": round(percentile(latencies, 0.95), 1) if latencies else None,
        "p99_ms": round(percentile(latencies, 0.99), 1) if latencies else None,
        "server_alive": True,
        "errors_sample": sorted(set(errors))[:5],
        **sampler.summary(),
    }


def failure_reason(level: dict, stress: dict) -> str:
    if "out_of_memory" in level["errors_sample"]:
        return "memory"
    memory = level.get("memory_max_pct")
    if memory is not None and memory >= stress["max_memory_pct"]:
        return "memory"
    cpu = level.get("cpu_avg_pct")
    if cpu is not None and cpu >= stress["max_cpu_pct"]:
        return "cpu"
    if level["error_rate_pct"] > stress["max_error_rate_pct"]:
        return "error_rate"
    if level["p95_ms"] is not None and level["p95_ms"] > stress["p95_ms"]:
        return "p95"
    if level["p99_ms"] is not None and level["p99_ms"] > stress["p99_ms"]:
        return "p99"
    return "pass"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--queries", type=Path, default=Path("queries"))
    parser.add_argument("--thresholds", type=Path, default=Path("bench/thresholds.json"))
    parser.add_argument("--engine", default="duckdb")
    parser.add_argument("--commit", default=None)
    parser.add_argument("--branch", default=None)
    parser.add_argument("--memory-limit", default="2GB")
    parser.add_argument("--md-out", type=Path, default=Path("bench/stress-report.md"))
    parser.add_argument("--json-out", type=Path, default=Path("bench/stress.json"))
    parser.add_argument("--history-entry-out", type=Path, default=Path("bench/history-entry.json"))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    thresholds = load_thresholds(args.thresholds)
    stress = thresholds["stress"]
    queries = load_queries(args.queries)
    by_name = {query["name"]: query for query in queries}
    unknown = [name for name in stress["workload"] if name not in by_name]
    if unknown:
        raise SystemExit(f"unknown queries in the stress workload: {', '.join(unknown)}")
    workload = [by_name[name] for name in stress["workload"]]
    weights = list(stress["workload"].values())
    deck = build_deck(workload, weights)

    memory_limit_bytes = 2 * 1024**3
    run_level(
        str(args.db),
        deck,
        1,
        stress["warmup_seconds"],
        stress["think_time_seconds"],
        args.memory_limit,
        memory_limit_bytes,
    )

    levels = []
    breaking = None
    for clients in stress["clients"]:
        level = run_level(
            str(args.db),
            deck,
            clients,
            stress["duration_seconds"],
            stress["think_time_seconds"],
            args.memory_limit,
            memory_limit_bytes,
        )
        level["verdict"] = failure_reason(level, stress)
        levels.append(level)
        if level["verdict"] != "pass":
            breaking = level
            break

    max_clients_ok = max(
        (level["clients"] for level in levels if level["verdict"] == "pass"), default=0
    )
    markdown = render_markdown(levels, stress, max_clients_ok, breaking)
    args.md_out.parent.mkdir(parents=True, exist_ok=True)
    args.md_out.write_text(markdown, encoding="utf-8")
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(
            {
                "engine": args.engine,
                "thresholds": stress,
                "levels": levels,
                "max_clients_ok": max_clients_ok,
                "breaking": breaking,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    reference = breaking or levels[-1]
    entry = {
        "commit": args.commit or os.environ.get("GITHUB_SHA", ""),
        "branch": args.branch or os.environ.get("GITHUB_REF_NAME", ""),
        "engine": args.engine,
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "max_users": max_clients_ok,
        "reason": reference["verdict"] if breaking else "none",
        "reason_text": REASONS[reference["verdict"] if breaking else "none"],
        "cpu_pct": reference.get("cpu_avg_pct"),
        "memory_pct": reference.get("memory_max_pct"),
    }
    args.history_entry_out.parent.mkdir(parents=True, exist_ok=True)
    args.history_entry_out.write_text(json.dumps(entry, indent=2) + "\n", encoding="utf-8")

    print(markdown)
    print(f"report: {args.md_out}\njson:   {args.json_out}\nentry:  {args.history_entry_out}")
    failed = max_clients_ok < stress["min_clients"]
    print(f"acceptance: {'PASS' if not failed else 'FAIL'}")
    if args.strict and failed:
        print(
            f"Only {max_clients_ok} users within SLA, minimum is {stress['min_clients']}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
