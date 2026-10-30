#!/usr/bin/env python3
"""Append one stress result to the gh-pages history file."""

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--entry", type=Path, required=True)
    args = parser.parse_args()

    entry = json.loads(args.entry.read_text(encoding="utf-8"))
    history = []
    if args.history.exists():
        history = json.loads(args.history.read_text(encoding="utf-8"))

    key = (entry.get("commit"), entry.get("engine"))
    history = [
        item for item in history if (item.get("commit"), item.get("engine")) != key
    ]
    history.append(entry)
    history.sort(key=lambda item: item.get("date", ""))
    args.history.write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")
    print(f"{len(history)} entries in {args.history}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
