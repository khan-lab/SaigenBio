# Verify a reconstructed result

Verification creates a new observed attempt and an explicit comparison with a preserved original. It tests a stated procedure under recorded conditions; matching results do not establish an unavailable historical code version or scientific correctness.

## Prepare and review

The agent identifies accepted input states, preserved input artifacts, preserved code/environment files, the exact command, declared outputs, prerequisites and resource/cost expectations. It then publishes a JSON proposal:

```sh
saigen verify propose --file verification.json --revision REV
saigen verify show
```

Example (replace IDs and executable path with actual records and runtime):

```json
{
  "originalStateId": "historical_result",
  "inputStateIds": ["source_table"],
  "inputArtifactIds": ["ar_input"],
  "codeArtifactIds": ["ar_script"],
  "command": ["/path/to/runtime/bin/python", "{code:0}", "--input", "{input:0}", "--output", "filtered.csv", "--min-dp", "10"],
  "outputs": ["filtered.csv"],
  "criteria": [
    {"originalArtifactId": "ar_original", "output": "filtered.csv", "method": "sha256"},
    {"originalArtifactId": "ar_original", "output": "filtered.csv", "method": "numeric-table", "keyColumns": ["sample"], "columns": ["depth", "value"], "atol": 0, "rtol": 0, "delimiter": ","}
  ],
  "reason": "Test the logged threshold using the preserved current script; historical code identity remains unknown.",
  "prerequisites": "Python standard library; no installation or download required.",
  "resources": "Small local teaching table; no network or paid compute."
}
```

Input artifacts must belong to declared input states; originals must belong to the original result. All compared and declared source artifacts must be preserved copies. Optional `environmentArtifactIds` preserves environment specifications; it does not automatically create or activate an environment. Optional `toolVersions` records declarations. Use `{code:N}` for preserved scripts and `{input:N}` for declared inputs. The executable path/hash and artifact hashes are bound to the reviewed proposal. Files read indirectly by code are not automatically discovered.

Attempts use an isolated working directory and preserved input/code copies. The runner is not a filesystem sandbox: inspect scripts before approval and avoid commands that explicitly write into the original working project.

No command runs during proposal or approval. The original detail screen shows prerequisites, declared resources, criteria and the configuration approval control. After user agreement, the agent records approval of the exact digest:

```sh
saigen verify approve --id PROPOSAL --digest DIGEST --revision REV
saigen verify execute --id PROPOSAL --revision NEXT_REV
```

The agent performs these commands; the researcher need not enter them. Browser approval does not launch execution. Approval is a declaration rather than authenticated human identity. Flexible mode still respects this explicit verification review checkpoint. Changed configuration or runtime requires a new proposal and approval. Missing dependencies remain prerequisites; this service does not install them.

## Inspect attempts and comparisons

Each execution creates its own attempt and comparison states. The comparison links the original and rerun; both originals and failed/repeated attempts remain preserved. A completed comparison state means the comparison operation finished, not that artifacts matched. Its title and details expose the outcome:

| Outcome | Meaning |
| --- | --- |
| match | All declared criteria matched and the command completed |
| different | All criteria were evaluated and differed |
| partial | Criteria have mixed outcomes, including unavailable comparisons |
| unavailable | No criterion could be evaluated |
| failed | The observed attempt did not complete successfully, even if a saved artifact matches |

SHA-256 tests exact bytes. Numeric-table comparison matches rows by exact, unique, nonempty keys and compares only the named numeric columns. It reports missing/added keys, differing values, example limits and ignored columns. Row order is irrelevant when keys match. It rejects malformed rows, missing columns, duplicate keys, nonnumeric values and NaN/infinity. The numeric row limit is 100,000 per artifact. No allele normalization or domain-specific semantic equivalence is inferred.

Numeric equality uses `abs(a-b) <= max(atol, rtol * max(abs(a), abs(b)))`. Both tolerances must be explicit, finite and nonnegative. A file can pass numeric criteria and fail byte equality because of formatting or row order. Other semantic comparators are not currently supported.

After an interrupted session, inspect `verify show`. A completed observed attempt can be compared without rerunning it:

```sh
saigen verify compare --id ATTEMPT --revision REV
```

If its supervisor was lost, `verify recover --id ATTEMPT --revision REV` checks supervisor liveness and records uncertainty rather than inferring success. If preparation never reached an observed attempt, inspect the recorded failure/gap and start a separate attempt. `verify cancel --id PROPOSAL --reason "..." --revision REV` prevents future executions; it does not terminate an active process.

## Reports

Reports preserve selected explanations, review context, verification configurations, observed attempt metadata and comparisons. Cited narrative and verification files are copied to `evidence/` in the frozen source bundle, capped at 5 MB per file and 20 MB total. Unavailable or oversized evidence retains hash/reference metadata and a warning. Original source contents are copied unchanged; select excerpts during reconstruction when full conversations are inappropriate.
