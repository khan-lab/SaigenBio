# Reconstruction review and verification design

This extends the existing-project journey without automatic discovery or execution. Source selection remains explicit; original files are read and preserved, not edited. A proposal may be incomplete and may include conflicting evidence.

## Review useful parts

Each proposed state and relationship has its own review status. A state can be accepted without accepting an uncertain incoming relationship. A relationship can be accepted only when all its endpoints are accepted. Rejecting an unused draft state also archives its still-draft incident relationships; accepted work is preserved. Whole-proposal buttons apply only to the remaining draft items. Reviewed and rejected items retain reviewer, time and optional reason. Archived items remain inspectable.

The detail screen shows state review controls and separately labelled relationship controls. It explains that accepting a historical claim is a review decision, not observed execution. Plans and verification runs cannot use draft or rejected inputs.

## Add later evidence

Use an explicit extension proposal to reference existing accepted state IDs, add new states or relationships, or supply additional citations for an existing state/relationship. Existing content and citations are not overwritten. References are checked against preserved source versions. Each evidence addition is a reviewable item; acceptance appends attributed evidence, while rejection leaves the target unchanged. Conflicting new statements remain alongside the earlier evidence. Structural corrections use rejection of an unused draft relationship and a new relationship, rather than editing accepted history.

Repeated proposals still use evidence identity to prevent silent duplication. Overlapping work must explicitly identify existing targets rather than create fresh copies. Automatic semantic merging is outside this design. Source hashes, target IDs and citation locations identify repeated evidence additions.

## Optional verification

The agent prepares a concrete verification proposal: preserved original result, accepted input states and artifact IDs, preserved code/environment files, explicit command, output names, comparison criteria, prerequisites and stated resource/cost expectations. Missing dependencies are shown before execution. No command runs while preparing, reviewing or approving a proposal.

Approval records the proposal digest and current revision. The agent executes the approved proposal through the CLI. Every attempt is a new observed result; retries never replace originals or earlier attempts. Approval is a declaration and does not authenticate a human identity. Changed configuration requires a new proposal and approval.

Comparisons are recorded separately and link original and rerun states. Initially supported criteria are exact SHA-256 equality and keyed CSV/TSV numeric comparison with explicit columns and absolute/relative tolerances. Numeric comparison reports missing keys, duplicate keys, invalid numbers and differences; it does not silently normalize alleles, reorder unkeyed rows, ignore NaNs, or infer scientific equivalence. Uncompared columns are explicitly identified. Other artifact types need a separately designed comparator.

Match means the stated criteria matched under the recorded conditions. Partial, different, unavailable and failed outcomes remain visible. A successful comparison does not establish the historical script version or scientific correctness. A completed attempt can be compared after an interrupted session without rerunning it.

The browser presents proposals, declared approval, attempts and comparisons; analysis execution remains a CLI/agent operation. Reports retain explanations, reconstruction evidence, verification criteria/results and their preserved sources in the frozen export.

## Acceptance evidence

A synthetic mixed-source fixture contains a chat/log parameter conflict, a script whose historical version is missing, preserved input/output files and methodological notes. Test review, selective rejection, later evidence, an authorized rerun, exact and numeric comparisons, restart/resume, and report export. Check original hashes throughout. Record the fresh-agent trial separately from deterministic integration checks and report any host/runtime limitation honestly. No biological analysis or broad workspace scan is required.
