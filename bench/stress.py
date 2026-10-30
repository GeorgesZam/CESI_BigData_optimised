#!/usr/bin/env python3
"""Concurrency stress test: how many users before the database breaks.

One user sends one request every `think_time_seconds`, drawing from a fixed
weighted mix of the queries in queries/. The ramp stops at the first level where
the database leaves the SLA:

- the server stops answering (crash, OOM kill, refused connection),
- memory reaches the limit,
- CPU saturates,
- the error rate exceeds the threshold,
- p95 or p99 exceeds its threshold.

The report leads with the breaking point and the reason. It also writes a JSON
entry for the single gh-pages history page.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import psutil
import psycopg

from benchmark import fmt_ms, load_queries, load_thresholds, percentile

REASONS = {
    "server_unreachable": "server stopped answering",
    "memory": "memory saturated",
    "cpu": "CPU saturated",
    "error_rate": "too many errors",
    "p95": "response time too slow (p95)",
    "p99": "response time too slow (p99)",
    "none": "no failure",
}


def build_deck(queries: list[dict], weights: list[int], seed: int = 42) -> list[dict]:
    deck = [query for query, weight in zip(queries, weights) for _ in range(weight)]
    random.Random(seed).shuffle(deck)
    return deck


class ResourceSampler:
    def __init__(self, container: str | None):
        self.container = container
        self.cpu: list[float] = []
        self.memory: list[float] = []
        self._stop = asyncio.Event()

    async def run(self) -> None:
        psutil.cpu_percent(None)
        while not self._stop.is_set():
            self.cpu.append(psutil.cpu_percent(None))
            self.memory.append(await asyncio.to_thread(self._memory_pct))
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=0.5)
            except asyncio.TimeoutError:
                pass

    def stop(self) -> None:
        self._stop.set()

    def _memory_pct(self) -> float:
        if self.container:
            try:
                result = subprocess.run(
                    [
                        "docker",
                        "stats",
                        "--no-stream",
                        "--format",
                        "{{.MemPerc}}",
                        self.container,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
                if result.returncode == 0 and result.stdout.strip():
                    return float(result.stdout.strip().rstrip("%"))
            except Exception:
                pass
        return psutil.virtual_memory().percent

    def summary(self) -> dict:
        return {
            "cpu_avg_pct": round(statistics.mean(self.cpu), 1) if self.cpu else None,
            "cpu_max_pct": round(max(self.cpu), 1) if self.cpu else None,
            "memory_max_pct": round(max(self.memory), 1) if self.memory else None,
        }


async def worker(dsn, deck, offset, deadline, think_time, latencies, errors):
    try:
        conn = await psycopg.AsyncConnection.connect(dsn, autocommit=True, connect_timeout=5)
    except Exception as exc:
        errors.append(f"connect:{type(exc).__name__}")
        return
    try:
        await conn.execute("SET jit = off")
        index = offset
        while time.perf_counter() < deadline:
            query = deck[index % len(deck)]
            index += 1
            started = time.perf_counter()
            try:
                await (await conn.execute(query["sql"])).fetchall()
                latencies.append((time.perf_counter() - started) * 1000.0)
            except Exception as exc:
                errors.append(type(exc).__name__)
                try:
                    await conn.close()
                except Exception:
                    pass
                try:
                    conn = await psycopg.AsyncConnection.connect(
                        dsn, autocommit=True, connect_timeout=5
                    )
                    await conn.execute("SET jit = off")
                except Exception as reconnect_exc:
                    errors.append(f"reconnect:{type(reconnect_exc).__name__}")
                    return
            remaining = deadline - time.perf_counter()
            if remaining > 0:
                await asyncio.sleep(min(think_time, remaining))
    finally:
        try:
            await conn.close()
        except Exception:
            pass


async def server_alive(dsn) -> bool:
    try:
        conn = await psycopg.AsyncConnection.connect(dsn, autocommit=True, connect_timeout=3)
    except Exception:
        return False
    try:
        await conn.execute("select 1")
        return True
    except Exception:
        return False
    finally:
        try:
            await conn.close()
        except Exception:
            pass


async def run_level(dsn, deck, clients, duration, think_time, container) -> dict:
    latencies: list[float] = []
    errors: list[str] = []
    sampler = ResourceSampler(container)
    sampler_task = asyncio.create_task(sampler.run())
    deadline = time.perf_counter() + duration
    tasks = [
        asyncio.create_task(
            worker(
                dsn,
                deck,
                (worker_id * 13) % len(deck),
                deadline,
                think_time,
                latencies,
                errors,
            )
        )
        for worker_id in range(clients)
    ]
    await asyncio.gather(*tasks)
    sampler.stop()
    await sampler_task
    alive = await server_alive(dsn)
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
        "server_alive": alive,
        "errors_sample": sorted(set(errors))[:5],
        **sampler.summary(),
    }


def failure_reason(level: dict, stress: dict) -> str:
    if not level["server_alive"]:
        return "server_unreachable"
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


def render_markdown(levels: list[dict], stress: dict, max_clients_ok: int, breaking: dict | None) -> str:
    lines = ["# Stress test report", ""]
    lines.append(
        f"- One user = one request every {stress['think_time_seconds']} s, "
        f"about {round(60 / stress['think_time_seconds'])} requests per minute"
    )
    lines.append(
        f"- Acceptance: p95 <= {stress['p95_ms']} ms, p99 <= {stress['p99_ms']} ms, "
        f"errors <= {stress['max_error_rate_pct']}%, CPU <= {stress['max_cpu_pct']}%, "
        f"memory <= {stress['max_memory_pct']}%"
    )
    lines.append(
        f"- Levels: {', '.join(str(value) for value in stress['clients'])} users, "
        f"{stress['duration_seconds']} s each after a {stress['warmup_seconds']} s warm-up"
    )
    lines.append("")
    verdict = max_clients_ok >= stress["min_clients"]
    if breaking is None:
        lines.append(f"**No failure up to {levels[-1]['clients']} users.**")
    else:
        word = "user" if breaking["clients"] == 1 else "users"
        lines.append(
            f"**Breaks at {breaking['clients']} {word}** — "
            f"{REASONS[breaking['verdict']]}."
        )
    lines.append(f"Max users within SLA: **{max_clients_ok}** — "
                 f"{'PASS' if verdict else 'FAIL'}")
    lines.append("")
    lines.append("| Users | Requests | Throughput (req/s) | p95 | p99 | CPU | Memory | Errors | Verdict |")
    lines.append("| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |")
    for level in levels:
        def value(key, suffix=""):
            item = level.get(key)
            return "-" if item is None else f"{item}{suffix}"
        lines.append(
            f"| {level['clients']} | {level['transactions']} | {level['throughput']} | "
            f"{fmt_ms(level['p95_ms']) if level['p95_ms'] is not None else '-'} | "
            f"{fmt_ms(level['p99_ms']) if level['p99_ms'] is not None else '-'} | "
            f"{value('cpu_avg_pct', '%')} | {value('memory_max_pct', '%')} | "
            f"{level['errors']} ({level['error_rate_pct']}%) | {level['verdict']} |"
        )
    lines.append("")
    lines.append("The load generator runs on the same machine as the database, so at high "
                 "concurrency it competes for CPU. The breaking point is a lower bound.")
    return "\n".join(lines) + "\n"


async def main_async(args) -> int:
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

    await run_level(
        args.dsn, deck, 1, stress["warmup_seconds"], stress["think_time_seconds"], args.container
    )

    levels = []
    breaking = None
    for clients in stress["clients"]:
        level = await run_level(
            args.dsn,
            deck,
            clients,
            stress["duration_seconds"],
            stress["think_time_seconds"],
            args.container,
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
        "commit_message": args.commit_message,
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", default="postgresql://postgres@localhost:5432/cesi")
    parser.add_argument("--queries", type=Path, default=Path("queries"))
    parser.add_argument("--thresholds", type=Path, default=Path("bench/thresholds.json"))
    parser.add_argument("--engine", default="postgres")
    parser.add_argument("--container", default=os.environ.get("PG_CONTAINER"))
    parser.add_argument("--commit", default=None)
    parser.add_argument("--commit-message", default="")
    parser.add_argument("--branch", default=None)
    parser.add_argument("--md-out", type=Path, default=Path("bench/stress-report.md"))
    parser.add_argument("--json-out", type=Path, default=Path("bench/stress.json"))
    parser.add_argument("--history-entry-out", type=Path, default=Path("bench/history-entry.json"))
    parser.add_argument("--strict", action="store_true", help="exit non-zero when max users is below min_clients")
    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
