# Local Snakemake workflows

Use a local workflow directory containing `Snakefile` or `workflow/Snakefile`, with Snakemake 9.27.x available on PATH. Set `SAIGEN_SNAKEMAKE` to the absolute launcher path if you use a separate environment. SaigenBio was tested with Snakemake 9.27.2. [Snakemake CLI reference](https://snakemake.readthedocs.io/en/stable/executing/cli.html)

Ask your agent to inspect the local Snakefile, use specific recorded inputs, and show a proposed run on the Canvas. The agent uses the shared [workflow commands](workflows.md) with `saigen workflow inspect --engine snakemake --source PATH`. Inspection inventories and fingerprints local files and checks the installed version. The Snakefile runs only when the agent executes the approved proposal. Snakemake dry runs can also evaluate workflow code and are outside static inspection.

## Proposal settings

Copy the `pipeline` identity from inspection and use the detected version in `engine`. The workflow directory should contain the Snakefile and local helper scripts and configuration. SaigenBio copies that directory for each attempt, excluding Git, SaigenBio, and Snakemake working data.

- `configuration.targets` lists explicit targets, preferably relative output filenames. `configuration.cores` defaults to 1.
- `configuration.parameters` supplies JSON values to Snakemake's config. Each recorded input binding supplies an additional config key whose value is the path to a verified copy of the artifact. A key belongs in either `parameters` or `inputBindings`.
- Use `mapping: {"rule": "summarize"}` to associate a stage with a distinct rule. Give each stage its expected output files relative to the workflow directory and review the stage dependencies before approval.

For example, a copy rule could use `input: config["records"]` and write `"copied.txt"`. The proposal binds the `records` key to a recorded input artifact. It declares `{"targets": ["copied.txt"], "cores": 1, "parameters": {}}` and expects `copied.txt` on the stage mapped to that rule.

## Execution and evidence

Execution uses the local executor with profiles disabled and records Snakemake job events, logs, source, and supplied configuration. The workflow code runs with the caller's permissions. Review its local code and external dependencies before approval.

SaigenBio completes a stage after the engine reports exactly one successful matching job and the expected files are declared by that job and present inside the attempt. Failed jobs remain failed. Rules with zero or multiple observed jobs remain unresolved. Use a pipeline with one output-producing job per mapped rule for this first release. Cluster execution, deployment profiles, dynamic job aggregation, live job updates on the Canvas, and resuming an attempt are outside this adapter's scope.

Run the synthetic integration test from the SaigenBio checkout with the supported engine available:

```sh
SAIGEN_TEST_SNAKEMAKE=1 python3 -B -m unittest discover -s tests -p test_snakemake_adapter.py
```
