"""Run paired delivery-routing trials in new, isolated project directories."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import itertools
import json
from pathlib import Path
import random
import shutil
import subprocess
import time


ROOT = Path(__file__).resolve().parent
VARIANTS = ("skill-chain", "project-workflow")
POLICIES = ("owner", "auto")
PROMPT = ("Read this project's AGENTS.md and deliver the assigned change in TASK.md under "
          "the project rules. Work inside this checkout with its local services. "
          "Complete all authorized actions and report the observed outcome.")


def prepare(target, variant, policy):
    shutil.copytree(ROOT / "shared", target)
    overlay = ROOT / "variants" / variant
    shutil.copy2(overlay / "AGENTS.md", target)
    if variant == "project-workflow":
        shutil.copy2(overlay / "WORKFLOW.md", target)
    else:
        for handoff in sorted((overlay / "handoffs").glob("*.md")):
            path = target / ".agents/skills" / handoff.stem / "SKILL.md"
            with path.open("a") as skill:
                skill.write("\n" + handoff.read_text())
    shutil.copy2(ROOT / "policies" / (policy + ".json"), target / "policy.json")


def trial(root, model, variant, policy, repeat):
    trial_id = f"{model}_{policy}_{repeat}_{variant}"
    evidence = root / trial_id
    evidence.mkdir()
    checkout = evidence / "project"
    prepare(checkout, variant, policy)
    argv = ["codex", "exec", "--ignore-user-config", "--ephemeral", "--skip-git-repo-check",
            "--sandbox", "workspace-write", "--disable", "apps", "--disable", "plugins",
            "--enable", "skip_host_skill_discovery", "-c", 'web_search="disabled"',
            "-c", 'model_reasoning_effort="low"', "-m", model, "--json", PROMPT]
    start = time.monotonic()
    with (evidence / "client.jsonl").open("w") as out, (evidence / "client.stderr").open("w") as err:
        try:
            code = subprocess.run(argv, cwd=checkout, stdout=out, stderr=err, timeout=420).returncode
        except subprocess.TimeoutExpired:
            code = 124
    record = dict(id=trial_id, model=model, variant=variant, policy=policy, repeat=repeat,
                  seconds=round(time.monotonic() - start, 2), exit_code=code)
    (evidence / "run.json").write_text(json.dumps(record) + "\n")
    print(trial_id, code, record["seconds"], flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="a new directory outside any existing project")
    parser.add_argument("--prepare", choices=VARIANTS, help="assemble one local harness without running a model")
    parser.add_argument("--policy", choices=POLICIES, default="owner", help="policy for --prepare")
    parser.add_argument("--models", nargs="+", default=["gpt-6-luna", "gpt-6.2-sol"])
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    if args.repeats < 1 or args.jobs < 1:
        parser.error("repeats and jobs must be positive")
    root = args.output.resolve()
    route = (ROOT / "variants/project-workflow/WORKFLOW.md").read_text()
    for handoff in (ROOT / "variants/skill-chain/handoffs").glob("*.md"):
        if route.count(handoff.read_text().strip()) != 1:
            parser.error(f"handoff differs between variants: {handoff.stem}")
    if args.prepare:
        prepare(root, args.prepare, args.policy)
        print(root)
        return
    root.mkdir(parents=True, exist_ok=False)
    pairs = list(itertools.product(args.models, POLICIES, range(1, args.repeats + 1)))
    random.Random(17).shuffle(pairs)
    jobs = []
    for i, (model, policy, repeat) in enumerate(pairs):
        for variant in (VARIANTS if i % 2 == 0 else reversed(VARIANTS)):
            jobs.append((root, model, variant, policy, repeat))
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(trial, *job) for job in jobs]
        for future in futures:
            future.result()


if __name__ == "__main__":
    main()
