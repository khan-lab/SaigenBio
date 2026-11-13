# Explore E. coli variants with SaigenBio

This walkthrough follows a researcher changing their mind: acquire data, filter at depth 5, plot, try log scaling, revisit depth 10, compare, and interpret. Send each prompt only after inspecting the previous result.

## 1. Prepare a fresh external workspace

From the source checkout, build and check a regular installation:

```bash
python3 -B scripts/check_installation.py --agent claude --with-quarto
```

Choose codex, claude, opencode, or antigravity with --agent. The printed trial workspace has an installed runtime, skill, and project instructions. All trial files stay outside the source checkout.

For this biological walkthrough, create a separate workspace alongside that trial's workspace, using the runtime path printed by the check:

```bash
/path/to/trial/runtime/bin/saigen setup --workspace /path/to/trial/exploration --agent claude --analysis-project projects/ecoli --viewer http://127.0.0.1:8767/
cd /path/to/trial/exploration
source ../runtime/bin/activate
saigen init --project projects/ecoli --name "E. coli threshold exploration"
saigen serve --project projects/ecoli --port 8767
```

This workspace has no synthetic fixture configured. Use a new directory for each rehearsal. Setup refuses to replace differing instruction files. Open http://127.0.0.1:8767/ and leave the viewer running. Choose another free port if needed and keep saigen-workspace.json consistent.

Open a new session in this exploration workspace using your chosen agent. See [agent integrations](agent-integrations.md). Enable workspace writes. Requesting a plan in normal mode lets the agent save proposals while waiting for scientific approval; a native mode that forbids writes cannot publish canvas nodes.

The canvas is editable by default: drag states to arrange them, or click a state to select its editing controls. Hover for about 650 ms to see a preview, then choose **Show detail →** to open its details. Report selection temporarily disables state dragging; cancelling it restores editing.

## 2. Explore and download

> I want to explore the E. coli dataset used in the Data Carpentry genomics lesson. Download its public variant-call table and explain what the samples represent. Show me a small sample summary before we decide how to analyze it. Please use the public source rather than copying files from my computer.

The public teaching table is available at:
https://raw.githubusercontent.com/datacarpentry/genomics-r-intro/main/episodes/data/combined_tidy_vcf.csv

Sources: [lesson dataset and sample descriptions](https://datacarpentry.github.io/organization-genomics/data.html), [lesson download example](https://datacarpentry.github.io/genomics-r-intro/06-data-visualization.html).

This is a processed variant-call table, not raw sequencing reads. Its acquisition can be recorded; earlier alignment and calling were not performed in this session. The lesson describes samples SRR2589044, SRR2584863, and SRR2584866 from generations 5,000, 15,000, and 50,000 respectively. The agent should verify downloaded columns and sample metadata instead of assuming their names.

Expected canvas:
- A dotted acquiring node appears while the recorded acquisition command runs, with no incoming arrow.
- The completed dataset node prioritizes a compact sample table if the agent produces one with the acquisition outputs. Otherwise it previews the downloaded CSV.
- Download command, declared source URL, timestamps, status, file hashes, and logs are in the node details.
- Unknown upstream execution remains explicitly unknown.

CSV/TSV previews show a bounded excerpt, not the full dataset. For a useful sample overview, the agent can produce a samples.tsv with a few biologically meaningful columns during acquisition. Raw FASTQ and VCF text are not automatically turned into sample metadata.

## 3. Filter

> Keep variant calls with reported depth (DP) of at least 5. Show the original count, retained count, and percentage removed for each sample. Then pause before plotting.

The agent should inspect the depth field and record the actual method. For this CSV example, a DP >= 5 table filter is appropriate after checking field meaning and missing values. This is not raw-read QC, nor an exact reproduction of vcfutils.pl varFilter, which has additional filtering behavior. Keep missing-depth handling explicit and include all three samples, even if one retains zero records.

Expected: dataset -> depth-5 results, including a count table.

## 4. Plot the three sampled generations

> Plot the retained variant counts for the three samples, ordered by generation. Label the samples and generations clearly.

Expected: a linear plot derived from the depth-5 count table. These are three sampled clones, not replicated populations; counts are not mutation rates.

## 5. Inspect the imbalance

> One sample dominates the chart. Can we try a logarithmic scale so the smaller counts are easier to see? Keep the original plot too.

Expected: a separate figure using the same counts. Explain how any zero counts are handled; do not silently drop them or introduce an undisclosed pseudocount. The figure should not rerun variant filtering.

## 6. Revisit the threshold

> My PhD TA asked what would happen if we required at least 10 supporting reads. Can we try that and make a comparable plot?

Expected: a new depth-10 branch from the original downloaded calls, retaining the depth-5 branch. Use matching sample order and clearly label the scale. Preserve actual script options so the changed threshold is visible in execution details.

## 7. Compare

> Compare the two thresholds. Which samples lose the most calls, in absolute numbers and percentages? Which variant calls are removed?

Expected: a comparison with both filtered results as inputs. Match variants by sample and chromosome, position, reference, and alternate allele; check duplicates and multi-allelic representation rather than comparing row numbers. Show retained and removed counts. A stricter numeric threshold should not add calls when other rules are identical.

## 8. Interpret and decide

> Does changing the threshold change our conclusion? Explain which observations remain consistent and what we would need to check before interpreting the differences biologically.

Keep conclusions proportional to this teaching dataset. Retained call counts alone do not establish causal variants, mutation rates, or the mechanism of a phenotype. Save the explanation as an annotation on the comparison state; a separate state is useful only if new evidence is generated.

The typical flow stays around 8–10 states. Do not create a node for every sentence or inspection command.

## Alternative: existing data

If files are already downloaded, configure their paths through --input during setup and ask the agent to inspect them. It should import existing evidence with snapshot and record checksums. It must not invent download commands, dates, or source provenance. If download logs exist, preserve them as evidence without claiming the wrapper observed their execution.

## Optional planning test

Before filtering, ask for a plan and require approval before analysis. Proposed result nodes should appear dotted without edges. After approval, each step adds its incoming animated edge and finalizes individually. Very short commands may complete between viewer polls.

For permission-blocked publication, the skill should request approval for the specific planning write when supported. Otherwise follow your agent's permission controls. Permission to publish does not approve analysis.

## Finish and export

Select the relevant states through Report, then Create PDF. Inspect plots, comparison notes, and evidence in the PDF and source ZIP. Export must not rerun analysis.

Keep the full project directory, including .saigen/. Stop the viewer with Ctrl+C.

Pass criteria: recorded acquisition or honest import; visible table/plot previews; correct branch parents; actual command differences; retained failed attempts; preserved files; and conclusions tied to recorded evidence. Repeat the same scientific prompts in each agent before claiming live compatibility.
