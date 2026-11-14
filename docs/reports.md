# PDF reports

Export reports from the analysis states already on the canvas. A report export does not need its own planned or completed node, and does not add analysis edges. If writing a report requires a new calculation or scientific comparison, record that analysis as a result state first, then include it in the export. Previously recorded report-generation runs remain part of the project's history.

## Select and export

Install Quarto with its bundled Typst engine and keep `quarto` on PATH. In the viewer, choose **Report**, then click states in the order you want to present them. Numbered badges show that order. Clicking a selected state removes it; selecting it again appends it. **Clear** resets the selection, **Cancel** leaves report mode, and **Create PDF** starts a local render with visible status. Download the PDF or its source bundle when ready. Report selection is separate from graph editing.

Reports read like an exported notebook: selected-state headings and recorded explanations, preserved scripts, recorded commands, then saved plots and table excerpts. Content flows across pages without a forced break per state. Identical state notes and action reasons appear once. Each preserved script version (identified by its full hash) is displayed at its first occurrence; later uses refer to that section. Changed script versions are displayed in full. Missing scripts are stated explicitly. Routine completion metadata and hash inventories stay in the source bundle; failed, planned, imported, and uncertain states remain labelled. Named omitted parents provide context; presentation order does not assert execution order or dependencies. No analysis runs, recorded commands execute, or biological interpretations are generated. Current statuses, missing evidence and unsupported figures are stated explicitly.

Each report is saved under `.saigen/reports/REPORT_ID/` with `report.pdf`, editable `report.qmd`, a controlled `_quarto.yml`, included figure files, `snapshot.json` and `manifest.json`. The ZIP includes those files. The manifest fixes the selected IDs/order and project revision, and hashes the selected snapshot, source and copied figures plus the resulting PDF. Graph edits after export do not change the saved report. From the extracted bundle, run:

```sh
quarto render report.qmd --to typst --output report.pdf --no-execute
```

The report aliases local paths. Labels embedded inside original figure files are preserved unchanged and can still contain paths or sensitive text. The selected snapshot is a record excerpt, not a full database backup or an analysis replay package; nonfigure source files are referenced by name and hash rather than bundled. The manifest pins source evidence, not a byte-identical PDF across Quarto/font versions.

The first version supports preserved SVG, PNG and JPEG figures, up to 20 MB per figure, 100 MB total, and 50 selected states. SVGs containing embedded/linked content or external declarations are omitted with a warning. External references are never read by reporting. Recorded Markdown is escaped as display text; executable blocks and includes are not interpreted. Rendering uses a fixed Quarto argument list, disabled code execution and a controlled project configuration. One report renders at a time, with a three-minute timeout. Downloads require the viewer session token; download links last for the server session, while saved report files remain on disk. A renderer error leaves its local `render.log` for inspection.

Script display uses verified, preserved UTF-8 copies up to 1 MB each. Script contents are displayed without execution; paths in displayed source are aliased. Table previews are bounded excerpts and may truncate rows, columns, and cell text. Multiple saved plots and table previews remain under their associated state.
