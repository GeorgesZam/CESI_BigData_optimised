#!/usr/bin/env python3
"""Concurrency stress test for the CESI healthcare PostgreSQL database.

The test ramps the number of concurrent clients and stops at the first failure:

- the server stops answering (crash, OOM kill, connection refused),
- the error rate exceeds the threshold,
- p95 or p99 latency exceeds the threshold,
- or every configured level passed.

It writes a Markdown report, a JSON file with every level, and two JSON files for
github-action-benchmark (latency, smaller is better; throughput, bigger is better).

The workload is a weighted mix of the queries in queries/, so each transaction
looks like an application request instead of one heavy analytics query.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
import time
from pathlib import Path

import psycopg

from benchmark import fmt_ms, load_queries, load_thresholds, percentile


def build_deck(queries: list[dict], weights: list[int], seed: int = 42) -> list[dict]:
    deck = [query for query, weight in zip(queries, weights) for _ in range(weight)]
    random.Random(seed).shuffle(deck)
    return deck


async def worker(dsn, deck, offset, deadline, latencies, errors):
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


async def run_level(dsn, deck, clients, duration) -> dict:
    latencies: list[float] = []
    errors: list[str] = []
    deadline = time.perf_counter() + duration
    tasks = [
        asyncio.create_task(
            worker(dsn, deck, (worker_id * 13) % len(deck), deadline, latencies, errors)
        )
        for worker_id in range(clients)
    ]
    await asyncio.gather(*tasks)
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
        "max_ms": round(max(latencies), 1) if latencies else None,
        "server_alive": alive,
        "errors_sample": sorted(set(errors))[:5],
    }


def failure_reason(level: dict, stress: dict) -> str:
    if not level["server_alive"]:
        return "server_unreachable"
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
        f"- Ramp: {', '.join(str(value) for value in stress['clients'])} clients, "
        f"{stress['duration_seconds']} s per level"
    )
    lines.append(
        f"- SLA: error rate <= {stress['max_error_rate_pct']}%, p95 <= {stress['p95_ms']} ms, "
        f"p99 <= {stress['p99_ms']} ms"
    )
    lines.append(f"- Minimum clients to sustain: {stress['min_clients']}")
    lines.append("")
    lines.append("| Clients | Transactions | Throughput (tx/s) | p50 (ms) | p95 (ms) | p99 (ms) | Max (ms) | Errors | Verdict |")
    lines.append("| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |")
    for level in levels:
        lines.append(
            f"| {level['clients']} | {level['transactions']} | {level['throughput']} | "
            f"{fmt_ms(level['p50_ms']) if level['p50_ms'] is not None else '-'} | "
            f"{fmt_ms(level['p95_ms']) if level['p95_ms'] is not None else '-'} | "
            f"{fmt_ms(level['p99_ms']) if level['p99_ms'] is not None else '-'} | "
            f"{fmt_ms(level['max_ms']) if level['max_ms'] is not None else '-'} | "
            f"{level['errors']} ({level['error_rate_pct']}%) | {level['verdict']} |"
        )
    lines.append("")
    if breaking is None:
        lines.append(f"No failure up to {levels[-1]['clients']} clients.")
    else:
        word = "client" if breaking["clients"] == 1 else "clients"
        lines.append(
            f"**Breaking point:** {breaking['clients']} {word}, reason `{breaking['verdict']}` "
            f"(p95 {breaking['p95_ms']} ms, p99 {breaking['p99_ms']} ms, "
            f"errors {breaking['error_rate_pct']}%)."
        )
    lines.append("")
    verdict = max_clients_ok >= stress["min_clients"]
    lines.append(f"**Max clients within SLA:** {max_clients_ok}")
    lines.append("")
    lines.append(f"Overall: **{'PASS' if verdict else 'FAIL'}**")
    lines.append("")
    lines.append("The client runs on the same 4 vCPU machine as PostgreSQL, so above a few "
                 "dozen clients the load generator competes with the database for CPU. "
                 "Treat the breaking point as a lower bound.")
    return "\n".join(lines) + "\n"


def action_entries(levels: list[dict], stress: dict, max_clients_ok: int) -> tuple[list[dict], list[dict]]:
    reference = next(
        (level for level in levels if level["clients"] == stress["reference_clients"]),
        None,
    )
    latency, throughput = [], []
    if reference is not None:
        for metric in ("p95_ms", "p99_ms", "error_rate_pct"):
            if reference[metric] is not None:
                latency.append(
                    {
                        "name": f"{metric}_at_{reference['clients']}_clients",
                        "unit": "ms" if metric != "error_rate_pct" else "%",
                        "value": reference[metric],
                    }
                )
        throughput.append(
            {
                "name": f"throughput_at_{reference['clients']}_clients",
                "unit": "tx/s",
                "value": reference["throughput"],
            }
        )
    last = levels[-1]
    if last["p95_ms"] is not None:
        latency.append({"name": "p95_at_last_level", "unit": "ms", "value": last["p95_ms"]})
    throughput.append({"name": "max_clients_ok", "unit": "clients", "value": max_clients_ok})
    return latency, throughput


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

    await run_level(args.dsn, deck, 1, stress["warmup_seconds"])

    levels = []
    breaking = None
    for clients in stress["clients"]:
        level = await run_level(args.dsn, deck, clients, stress["duration_seconds"])
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
    latency, throughput = action_entries(levels, stress, max_clients_ok)
    args.action_latency_out.parent.mkdir(parents=True, exist_ok=True)
    args.action_latency_out.write_text(json.dumps(latency, indent=2) + "\n", encoding="utf-8")
    args.action_throughput_out.parent.mkdir(parents=True, exist_ok=True)
    args.action_throughput_out.write_text(json.dumps(throughput, indent=2) + "\n", encoding="utf-8")

    print(markdown)
    print(f"report: {args.md_out}\njson:   {args.json_out}")
    failed = max_clients_ok < stress["min_clients"]
    print(f"acceptance: {'PASS' if not failed else 'FAIL'}")
    if args.strict and failed:
        print(
            f"Only {max_clients_ok} clients within SLA, minimum is {stress['min_clients']}",
            file=sys.stderr,
        )
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", default="postgresql://postgres@localhost:5432/cesi")
    parser.add_argument("--queries", type=Path, default=Path("queries"))
    parser.add_argument("--thresholds", type=Path, default=Path("bench/thresholds.json"))
    parser.add_argument("--md-out", type=Path, default=Path("bench/stress-report.md"))
    parser.add_argument("--json-out", type=Path, default=Path("bench/stress.json"))
    parser.add_argument("--action-latency-out", type=Path, default=Path("bench/action-stress-latency.json"))
    parser.add_argument("--action-throughput-out", type=Path, default=Path("bench/action-stress-throughput.json"))
    parser.add_argument("--strict", action="store_true", help="exit non-zero when max_clients_ok is below min_clients")
    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
