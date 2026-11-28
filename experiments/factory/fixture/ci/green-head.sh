#!/bin/sh
# Check the required CI for the open PR at this checkout's exact commit.
set -eu
head=$(git rev-parse HEAD)
git diff --quiet HEAD -- . ':!.scratch'
test "$(gh pr view --json state -q .state)" = OPEN
test "$(gh pr view --json baseRefName -q .baseRefName)" = main
test "$(gh pr view --json headRefOid -q .headRefOid)" = "$head"
gh pr checks --required
test "$(gh pr view --json headRefOid -q .headRefOid)" = "$head"
