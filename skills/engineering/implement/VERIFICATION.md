# Local Verify

Run one local pass after review corrections and affected tests, before opening a PR
or waiting for CI. Cover every required scenario of the delivery together. The
project's testing and acceptance rules determine applicability, evidence location
and who verifies. If independence is required, use a fresh verifier who did not
implement the change.

1. Take the task/spec, expected outcomes, immutable base and corrected revision,
   both review reports, dispositions and changes since review. Identify the required
   scenarios, roles and data. Record a missing expectation as unresolved.
2. Confirm the environment is ready and the running or inspected result corresponds
   to the corrected revision. Use the project's startup instructions, services and
   permitted test data. An unavailable prerequisite leaves dependent criteria open.
3. Perform each real action through its public entry point. Observe the result and
   material side effects. Where the project requires independent proof of a bug fix,
   reproduce the failure on the base in an isolated owned context and the success
   on the fix. Record the commands, outputs and both revisions.
4. For each criterion record action, expectation, observation including side effects,
   checked revision, result and evidence. Use an inspected screenshot for visible
   state, a recording for motion, or command output, data or measurements for a CLI,
   service or performance claim. Record the source and location of each artifact
   under the project's data rules.
5. Return the local verdict, coverage, limits and criterion records to the delivery
   author. Distinguish a demonstrated product failure from an environment blocker.
   For either, leave the required criterion open and identify the defect or the
   missing prerequisite. Delivery waits. Record duration or token usage if required,
   with unavailable measurements marked as such.

A successful local pass completes Verify for this delivery. Carry its original
revision and observations forward alongside any subsequent edits, affected tests
and final CI result.
