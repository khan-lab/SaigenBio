# Existing-analysis proposal

All relative file paths are resolved from the SaigenBio workspace. Source files and selected result files are preserved locally. Use stable, unique IDs. The command requires the current project revision from `saigen flow`.

```json
{
  "id": "history1",
  "sources": {"notes": "notes.md", "script": "analysis.py"},
  "states": [
    {"id": "old_input", "title": "Original table", "files": ["data.csv"], "evidence": [{"source": "notes", "location": "lines 1–8", "kind": "direct", "note": "The file exists; earlier creation is unknown."}]},
    {"id": "old_result", "title": "Filtered table", "files": ["filtered.csv"], "note": "Code version is unresolved.", "evidence": [{"source": "notes", "location": "lines 9–20", "kind": "reported", "note": "Conversation reports this result."}]}
  ],
  "connections": [
    {"from": ["old_input"], "to": "old_result", "label": "Depth filter", "command": "python analysis.py --min-depth 5", "evidence": [{"source": "script", "location": "lines 10–18", "kind": "inferred", "note": "Current script implements the filter; its historical execution is unresolved."}]}
  ]
}
```

A proposal can omit connections when relationships are unknown. Evidence locations are author-supplied citations, not automatically verified line matches. Multiple entries can document contradictions. Include preserved log or Git-summary files as additional named sources. Preserve originals when creating any summary, and identify its author and original references.

Repeated evidence graphs are rejected independently of proposal IDs, state IDs, source aliases, file paths and display titles. Identity uses preserved source hashes and citation locations, result-file hashes, and graph relationships. This detects repeat submissions, not semantic overlap between different excerpts or partially overlapping graphs.

For a corrected proposal, reject the earlier draft, use new IDs, and add this top-level field:

```json
"relation": {"proposal": "history1", "kind": "revision", "reason": "Correct the source attribution after review."}
```

For an intentional alternative interpretation, use `"kind": "alternative"` and explain why both should remain. The related proposal must exist; a revision must refer to a rejected proposal. Changing IDs alone is not a revision.

`saigen reconstruct show --id history1` returns the original `spec` alongside `graph.states` and `graph.actions`, which reflect current edits. Resume from `graph`; do not overwrite user corrections with `spec`. `graph.source` is `current` or, after rejection, `archive`. The entry also includes `projectRevision`, review status/attribution and lists of any missing state or action IDs.
