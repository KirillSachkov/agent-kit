# Predefined evaluation

Each assignment adds a CSV field to one local CLI. Both harnesses use exactly the same leaf procedures, project services, policy, task, model effort and prompt. The six handoff paragraphs are the same text. A places each paragraph in its skill. B puts the six together in a project workflow. This compares instruction organization within an interactive agent, using compact experimental skills.

A strict success requires a completed model invocation and all of the following observed properties:

1. The final CLI exports the extended header, a discount and the default for a missing value, with ordinary CSV escaping.
2. The review service ran once, after implementation, with two overlapping read-only reviewers on the same snapshot, one standards finding and a passing Spec result.
3. One correction updated the documentation example, and an affected test passed on that corrected snapshot after review and before Verify.
4. Local Verify ran once successfully on that snapshot, before a single PR was opened.
5. Packaging CI failed, the package declaration was fixed, affected tests passed on the changed candidate, then CI passed on it. No new review or Verify.
6. Classification ran once after green CI, on its revision, and returned the project's expected status.
7. The PR records the real review, Verify and final CI revisions, status, and a description of the later correction. For owner review it asks for an action in the PR. Assess the note's meaning manually.
8. An automatic delivery performed one successful merge. An owner-required delivery left the PR open with no merge attempt.

Record infra failures separately, all attempted runs, wall time and client-reported usage. These doubles test the coordinating agent. They do not measure the competence of independent LLM reviewers, the classifier, real CI or the live Git host. Two repeats per case are a pilot, not a statistically reliable model ranking.
