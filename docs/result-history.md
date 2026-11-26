# Understand results and decisions

State details use four principal sections:

| Section | Shows |
| --- | --- |
| What | Intended result, recorded files, and separately attributed questions, findings, interpretations and limitations |
| Why | Decisions, rationale, alternatives, agreement basis, stated action purposes and replacement relationships |
| Who | Declared proposers, contributors, approval participants, execution actors, reviewers and recorders, associated with their records |
| When | Recorder event times and expandable event records; reported historical dates stay with their statements |

**How** expands methods, parameters, commands, scripts and execution evidence. **Where** expands source states, input/output files and references. The detail screen shows sections when they have content. Ordinary notes remain annotations; a successful execution does not establish a biological conclusion.

## Add or correct an explanation

Open a state and choose **Add explanation**. Select a scientific question, finding, interpretation, limitation, decision, or replacement relationship. Decisions can include rationale, alternatives with tradeoffs, and the basis for agreement. Participants and evidence are optional; incomplete records remain useful.

Choose **Correct a recorded explanation** to append a correction. Earlier versions remain expandable and link to their correction. Normal title/note editing remains available and appears in the timeline. Explanations shared across states retain their scope when corrected.

Names and roles are declarations. An agent recording an approval is not automatically the person who agreed. Evidence classifications are direct, reported, inferred and unresolved; selecting one does not authenticate a participant or prove execution. Cite specific source lines, sections, panels or events. The UI supports references to registered files and source states; CLI documents can also cite numeric event revisions.

Historical dates are optional, include a timezone, and remain separate from the recording date. An imported claim about an earlier decision must not be presented as a decision observed by SaigenBio.

## AI-agent and CLI recording

Use the current revision from `saigen flow`:

```sh
saigen explain --file decision.json --revision REV --actor "Research agent"
saigen story STATE_ID
```

Example document (replace IDs with existing records):

```json
{
  "kind": "decision",
  "states": ["depth5"],
  "summary": "Use DP >= 5 for the exploratory comparison",
  "rationale": "Retain weaker calls to inspect their sensitivity to a stricter threshold.",
  "alternatives": [{"option": "DP >= 10", "reason": "Keep as a separate comparison."}],
  "agreementBasis": "The researcher requested a threshold comparison in the cited excerpt.",
  "participants": [{"name": "Researcher", "role": "approver"}],
  "evidenceKind": "reported",
  "evidence": [{"type": "artifact", "id": "ar_excerpt", "location": "JSONL lines 42–45"}]
}
```

Statement kinds are `question`, `finding`, `interpretation` and `limitation`; these need only `kind`, `states` and `summary`. Optional `actions` narrows the scope to particular incoming actions. Reference types are `artifact`, `state` and `event` (numeric revision). Preserve conversation sources through import or reconstruction before referencing them.

Other optional fields are `historicalAt` (ISO timestamp with timezone) and `supersedes` (the latest explanation ID being corrected). Corrections keep the same kind and state scope. Participant roles are `proposer`, `contributor`, `approver`, `executor` and `recorder`. Recording an explanation never grants execution approval or changes workflow configuration approval.

## Plans, retries and archived work

An executed plan retains its launch-time snapshot. Details also show the earliest recorded proposal and subsequent edit events where available. New snapshots retain proposer attribution; missing evidence on older records stays missing. Decisions link to stable state IDs and survive execution transitions.

A failed attempt remains failed. Record a retry separately. To explain a replacement, append:

```json
{
  "kind": "replacement",
  "states": ["earlier_attempt"],
  "replacementStateId": "replacement_plan",
  "summary": "Retry with the corrected input mapping."
}
```

This records a relationship and reason; it does not change execution status or cancel work. Replacement cycles are rejected. **Archive** on the canvas opens removed standalone plans, cancelled workflow proposals and rejected reconstructions. Their details remain accessible, including through replacement links. Undo can restore an eligible removed plan. IDs referenced by explanation history cannot be reused for unrelated new states.

Use **Select nodes** in Individual nodes or an opened group. Click or tap cards to toggle selection, then choose **Archive** from the selection menu. A single result also offers **Archive from canvas** in its detail menu. The change takes effect immediately, and **⌘Z / Ctrl+Z** restores a batch in one step.

In **Filter → Archived**, open a result to inspect its evidence or choose **Restore to canvas**. Archived results still appear as linked inputs in downstream details. They return to their recorded group and position on restoration, and bookmarked results return to **Saved**.

Next steps are linked plans with their own details, rather than a permanent Future section. Reasons and chronology are never inferred from canvas position, commands or later outcomes. See [existing-analysis reconstruction](getting-started.md#bring-in-an-existing-analysis) for importing historical evidence.
