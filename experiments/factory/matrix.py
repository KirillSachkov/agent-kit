#!/usr/bin/env python3
"""Run a matrix of bench trials in parallel and print one line per cell."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import itertools
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def trial(root, situation, entry, agent, model, repeat, timeout):
    folder = root / f"{situation}_{entry}_{agent}_{model.replace('/', '-')}_{repeat}"
    subprocess.run([sys.executable, str(HERE / "bench.py"), str(folder), "--situation", situation, "--entry", entry,
                    "--agent", agent, "--model", model, "--timeout", str(timeout)], capture_output=True, text=True)
    result = folder / "result.json"
    facts = json.loads(result.read_text()) if result.is_file() else {"pass": False, "final_stage": "no result"}
    print(folder.name, "PASS" if facts["pass"] else "FAIL", facts.get("final_stage"), facts.get("cost_usd"), facts.get("seconds"), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--situations", nargs="+", default=["happy", "verify-blocked", "ci-fix", "ci-outage", "spec", "rework"])
    parser.add_argument("--entries", nargs="+", default=["run-pipeline"])
    parser.add_argument("--agent", default="claude")
    parser.add_argument("--models", nargs="+", default=["haiku", "sonnet"])
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=1200)
    args = parser.parse_args()
    args.root.mkdir(parents=True)
    cells = itertools.product(args.situations, args.entries, args.models, range(1, args.repeats + 1))
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for situation, entry, model, repeat in cells:
            pool.submit(trial, args.root.resolve(), situation, entry, args.agent, model, repeat, args.timeout)


if __name__ == "__main__":
    main()
