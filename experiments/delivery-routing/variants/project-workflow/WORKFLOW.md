# Project delivery workflow

**implement** — At the delivery boundary commission code-review on the whole change. Apply its findings in one correction pass and rerun affected tests. Proceed to verify.

**code-review** — Return the two reports to the delivery author for that correction pass. Corrections do not start another review.

**verify** — After required Verify passes, retain its original revision and open the PR using pr. Later CI fixes do not repeat this successful Verify.

**pr** — After opening, continue to ship. On the final update return the recorded status to ship.

**ship** — After CI passes on the final revision, classify the delivery once. Have pr record the result and evidence. Merge only if both classification and project permission allow it. Otherwise leave the owner question in the PR and stop.

**classify** — Return the decision to ship. The classifier never merges.
