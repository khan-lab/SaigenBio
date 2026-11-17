# Verification of existing evidence

Verification is optional. Inspect the original and its evidence first. Explain the selected procedure, preserved inputs/code, missing dependencies, resource expectations and artifact-specific comparison criteria. Obtain agreement before executing that concrete proposal; imported commands do not authorize execution.

Publish using `saigen verify propose --file verification.json --revision REV`, then inspect `saigen verify show`. Required JSON fields:

- `originalStateId`: accepted original result.
- `inputStateIds` and `inputArtifactIds`: accepted inputs and preserved registered artifacts belonging to them.
- `codeArtifactIds`: preserved code versions to execute.
- `command`: argv, with an existing executable and `{code:N}` / `{input:N}` placeholders.
- `outputs`: relative files expected from the isolated attempt.
- `criteria`: objects with `originalArtifactId`, `output`, and `method`.
- `reason`, `prerequisites`, `resources`: concrete rationale, preparation needs, and declared local/compute/cost expectations. Unknown requirements stay explicit.

Optional `environmentArtifactIds` and `toolVersions` preserve environment specifications and declarations, not an automatically recreated environment. Preparation or installation must fit the user's authorized scope and host permissions. Artifact hashes and runtime path/hash are bound to approval. Use preserved code placeholders rather than mutable script paths. Unlisted transitive file dependencies are not discovered automatically.

Methods: `sha256` for exact byte equality; `numeric-table` requires unique `keyColumns`, numeric `columns`, explicit finite nonnegative `atol` and `rtol`, and optional delimiter comma or tab. Numeric matching uses exact row keys, reports missing/extra keys and ignored columns, rejects duplicates and non-finite values, and applies `abs(a-b) <= max(atol, rtol * max(abs(a),abs(b)))`. No arbitrary biological/semantic comparator is implied. Numeric tables are limited to 100,000 rows per artifact.

After user agreement, record `saigen verify approve --id PROPOSAL --digest DIGEST --revision REV`, then `saigen verify execute --id PROPOSAL --revision NEXT_REV`. Browser approval also records agreement without executing. These checkpoints apply in Flexible mode. Do not claim the recorder of approval is an authenticated human approver. Changed configuration needs a new proposal.

Inspect the observed attempt, actual outputs and comparison, not just the process return code. Outcomes are match, different, partial, unavailable or failed; a failed attempt remains failed even if an artifact matches. Matching criteria under current recorded conditions do not prove the missing historical code version or scientific conclusion. Preserve originals; retries create separate attempts and comparison states.

Resume with `verify show`; `verify compare --id ATTEMPT --revision REV` compares an existing finished attempt without rerunning. For a lost supervisor, `verify recover` checks liveness and records unknown completion. A preparation gap with no observed attempt cannot be promoted to success. `verify cancel --id PROPOSAL --reason ... --revision REV` prevents future runs but does not stop an active process.
