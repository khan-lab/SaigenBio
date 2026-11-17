# PDF reports

Export reports from the analysis states already on the canvas. A report export does not need its own planned or completed node, and does not add analysis edges. If writing a report requires a new calculation or scientific comparison, record that analysis as a result state first, then include it in the export. Previously recorded report-generation runs remain part of the project's history.

## Select and export

Install Quarto with its bundled Typst engine and keep `quarto` on PATH. In the viewer, choose **Report**, then click states in the order you want to present them. Numbered badges show that order. Clicking a selected state removes it; selecting it again appends it. **Clear** resets the selection, **Cancel** leaves report mode, then choose a template and use **Preview contents** before **Export PDF** starts a local render with visible status. Download the PDF or its source bundle when ready. Report selection is separate from graph editing.

Reports read like an exported notebook: selected-state headings and recorded explanations, preserved script excerpts (or full scripts), recorded commands, then saved plots and table excerpts. Content flows across pages without a forced break per state. Identical state notes and action reasons appear once. Each preserved script version (identified by its full hash) is displayed at its first occurrence; later uses refer to that section. Changed script versions remain distinct; the notebook prefers explicitly selected excerpts when available. Missing scripts are stated explicitly. Routine completion metadata and hash inventories stay in the source bundle; failed, planned, imported, and uncertain states remain labelled. Named omitted parents provide context; presentation order does not assert execution order or dependencies. No analysis runs, recorded commands execute, or biological interpretations are generated. Current statuses, missing evidence and unsupported figures are stated explicitly.

Each report is saved under `.saigen/reports/REPORT_ID/` with `report.pdf`, editable `report.qmd`, a controlled `_quarto.yml`, included figure files, `snapshot.json` and `manifest.json`. The ZIP includes those files. The manifest fixes the selected IDs/order and project revision, and hashes the selected snapshot, source and copied figures plus the resulting PDF. Graph edits after export do not change the saved report. From the extracted bundle, run:

```sh
quarto render report.qmd --to typst --output report.pdf --no-execute
```

The report aliases local paths. Labels embedded inside original figure files are preserved unchanged and can still contain paths or sensitive text. The selected snapshot is a record excerpt, not a full database backup or an analysis replay package; nonfigure source files are referenced by name and hash rather than bundled. The manifest pins source evidence, not a byte-identical PDF across Quarto/font versions.

The first version supports preserved SVG, PNG and JPEG figures, up to 20 MB per figure, 100 MB total, and 50 selected states. SVGs containing embedded/linked content or external declarations are omitted with a warning. External references are never read by reporting. Recorded Markdown is escaped as display text; executable blocks and includes are not interpreted. Rendering uses a fixed Quarto argument list, disabled code execution and a controlled project configuration. One report renders at a time, with a three-minute timeout. Downloads require the viewer session token; download links last for the server session, while saved report files remain on disk. A renderer error leaves its local `render.log` for inspection.

Script display uses verified, preserved UTF-8 copies up to 1 MB each. Script contents are displayed without execution; paths in displayed source are aliased. Table previews are bounded excerpts and may truncate rows, columns, and cell text. Multiple saved plots and table previews remain under their associated state.

## Bundled templates and contents preview

After selecting states, choose a template and click **Preview contents**. The dialog shows the template's purpose, selected state order and statuses, included sections, warnings, and frozen project revision. This is a contents outline, not a rendered PDF. Click **Export PDF**, then download the PDF or source bundle when ready. Changing the selection or template requires a new preview. Canvas edits after preview do not change that preview's exported evidence.

| Template | Presentation |
| --- | --- |
| Results summary | Figures, table excerpts, recorded explanations and brief method context |
| Analysis notebook (default) | Recorded explanations, methods, selected script excerpts (or full scripts when none were selected), commands, execution notes and results |
| Reproducibility appendix | Declared input/output identities, software information, detailed commands, full preserved scripts and saved evidence |

All templates retain the same selected snapshot and artifact inventory. Planned, imported, failed and uncertain evidence remains labeled; missing explanations are stated rather than generated. Workflow methods and supplied parameters remain declarations, and workflow-wide bindings do not establish stage-level consumption. Recorded script excerpts are checked against preserved source before display. Presentation may omit full source without implying that the evidence is missing.

The bundle also contains `report-template.json`. The manifest records its template ID, version and definition digest, and hashes both the template definition and generated Quarto source. All formatting needed for rendering is in the exported `report.qmd` and controlled `_quarto.yml`; re-rendering does not require SaigenBio. Nonfigure source files remain references by identity, rather than promised downloadable copies. These documents are neither executable notebooks nor complete environment replay packages.

The existing `POST /api/reports` API still starts rendering directly and defaults to `analysis-notebook` when `template` is omitted. It also accepts `results-summary` and `reproducibility-appendix`. For reviewed exports, `POST /api/reports/preview` accepts `selected`, `revision` and `template`; then `POST /api/reports/ID/render` accepts the preview's `revision`. These use the existing session-token and origin protections. Preview prepares sources and copies verified figures without invoking Quarto. Preview/export links last for the server session, and prepared reports remain on disk. User-supplied templates and extensions are not supported.

To validate all templates with synthetic fixtures outside the checkout:

```sh
python3 scripts/check_report_templates.py --destination /path/to/new/external/check
```

This renders each template and independently re-renders its extracted source bundle using Quarto/Typst. It does not perform biological analysis.
