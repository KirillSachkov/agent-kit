---
name: verify-greet
description: "Drive the greet command-line app the way a user does and report what happened. Use when asked to verify behaviour of greet or of a task in this repo."
---

# Verify greet

greet is a short-lived CLI. There is no server: each drive is one command.

## Doctor

Run `python3 --version` and `test -f greet.py`. If `.verify-env` is missing, the verification environment is not provisioned: stop and report `BLOCKED`.

## Drive

Run the command exactly as a user would, from the repo root, for each scenario of the task: `python3 greet.py <arguments>`. Capture stdout, stderr and the exit code of every run.

## Evidence

Save each run's command and output to `.evidence/<scenario>.txt`. Exercise the real command, never a helper function.

## Report

Write `.evidence/report.md` and return the same text. Its first line is `Verdict: PASS`, `Verdict: PASS+NOTES`, `Verdict: FAIL` or `Verdict: BLOCKED`. Then `Commit: <sha>`, and one line per scenario: what was run, what was observed, which evidence file shows it. `FAIL` means the product misbehaved; `BLOCKED` means the environment kept a scenario from running.

## Cleanup

Nothing to tear down. Keep `.evidence/`.
