# Local Nextflow workflows

The first Nextflow adapter supports local pipeline directories containing `main.nf`, JSON parameters, recorded file inputs, and explicit one-task-per-stage mappings. It was tested with Nextflow 25.10.4 and Java 17 on macOS. This is a constrained integration, not general support for nf-core pipelines or arbitrary dynamic workflows.

## Agent workflow

The agent should inspect the available engine and local pipeline, publish a concrete proposal using existing input states, show it to the user, obtain agreement, record approval, and launch that approved proposal. EDA is optional.

```sh
saigen --project /path/to/project workflow engines
saigen --project /path/to/project workflow inspect --engine nextflow --source /path/to/pipeline
saigen --project /path/to/project workflow propose --spec proposal.json --revision REVISION
saigen --project /path/to/project workflow show PROPOSAL_ID
saigen --project /path/to/project workflow approve PROPOSAL_ID --digest DIGEST --revision REVISION
saigen --project /path/to/project workflow execute PROPOSAL_ID --revision REVISION_AFTER_APPROVAL
saigen --project /path/to/project workflow status RUN_ID
saigen --project /path/to/project workflow recover
```

Execution accepts no parameter overrides. A changed configuration requires a new proposal and matching approval. Approval is declared by the agent after user agreement, not authenticated human identity. Flexible mode does not bypass this review checkpoint.

Use `SAIGEN_NEXTFLOW=/absolute/path/to/nextflow` for a separately installed launcher. Java and Nextflow runtime settings remain the caller's environment; SaigenBio does not change global installations or install dependencies automatically. See [official installation requirements](https://docs.seqera.io/nextflow/install).

Static inspection reads source files and queries the engine version; it does not resolve the pipeline DAG or evaluate its scientific code. Source and helper files are hashed and copied into a separate attempt directory. Recorded input bytes and the detected engine version are verified before launch. The pipeline identity returned by inspection can be used in the proposal's `pipeline` field.

## Proposal configuration

Use `configuration: {"parameters": {...}}` and a stage `mapping: {"process": "FILTER"}`. Match the qualified process name exactly. Input binding names become Nextflow parameter names and refer to verified input copies. They cannot also be supplied in parameters. Each stage must declare at least one relative expected output path within that task's work directory.

A pipeline config, if present, is copied with source. Launch uses explicit `-C` configuration files to exclude ambient config. The integration requests the local executor and a trace with task, process, status, exit, attempt and work-directory fields. It preserves the generated configuration, parameter file, source, task scripts, engine logs and trace. Source identity does not capture external includes, plugins, containers, external tools, secrets, network resources or host environment dependencies. Execution evaluates pipeline code with the permissions of its caller; this integration is not a sandbox. Source config selectors can affect behavior and must be reviewed with the proposal.

## Results and limits

The command remains in the foreground. Progress is available at workflow-run level; task and canvas results are finalized when the engine exits. Stage cards remain planned during execution. Continuous task monitoring and interactive workflow review UI are future work.

A stage becomes completed only when exactly one matching task completed with exit zero and every promised output is present inside that attempt's task directory. Missing outputs fail the stage even if Nextflow exits zero. More than one task row, no matching row, cached records and unresolved conditions remain unknown rather than inferred successful. Raw trace observations preserve attempts and statuses. Stage dependencies come from the reviewed mapping and are labeled as such; they are not independently observed file-level lineage.

Failed stages and unresolved stages retain distinct statuses. Re-execution creates new result states and keeps earlier outputs. Resume and cache reuse are not supported by this release. Engine session identity is read from preserved local execution history. Ctrl+C and SIGTERM terminate the foreground process group and record cancellation. After a lost supervisor, `workflow recover` marks the run unknown when its recorded process no longer exists; it neither infers completion nor attaches to an orphaned engine. PID reuse may conservatively prevent automatic recovery.

## Reproduce the real test

The example in `examples/workflows/datacarpentry-variants/` is a SaigenBio-authored teaching pipeline for the Data Carpentry processed E. coli variant table. It filters by QUAL and counts variants by sample; it does not perform variant calling.

Download the [lesson CSV](https://raw.githubusercontent.com/datacarpentry/genomics-r-intro/main/episodes/data/combined_tidy_vcf.csv) into an external workspace. With Nextflow and compatible Java configured:

```sh
python3 -B scripts/check_nextflow.py \
  --destination ../SaigenBio-lab/validation/nextflow-new-trial \
  --dataset /outside/path/combined_tidy_vcf.csv
```

The destination must be new and external to the checkout. The test copies pipeline source there and records the input. It checks planned states before execution, approval enforcement, independently calculated counts, deliberate task failure, missing promised output, source drift, and preservation of earlier states on rerun. It writes `nextflow-check.json` and retains the project and execution evidence for inspection. This is an explicit integration test that executes local processes; it is separate from the unit suite.
