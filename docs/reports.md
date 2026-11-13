# PDF reports

## Select and export

Install Quarto with its bundled Typst engine and keep `quarto` on PATH. In the viewer, choose **Report**, then click states in the order you want to present them. Numbered badges show that order. Clicking a selected state removes it; selecting it again appends it. **Clear** resets the selection, **Cancel** leaves report mode, and **Create PDF** starts a local render with visible status. Download the PDF or its source bundle when ready. Report selection is separate from graph editing.

Reports include only the selected states, their saved figures, recorded notes, incoming action reasons and commands, and compact source references. Named omitted parents provide context; presentation order does not assert execution order or dependencies. No analysis runs, recorded commands execute, or biological interpretations are generated. Current statuses, missing evidence and unsupported figures are stated explicitly.

Each report is saved under `.saigen/reports/REPORT_ID/` with `report.pdf`, editable `report.qmd`, a controlled `_quarto.yml`, included figure files, `snapshot.json` and `manifest.json`. The ZIP includes those files. The manifest fixes the selected IDs/order and project revision, and hashes the selected snapshot, source and copied figures plus the resulting PDF. Graph edits after export do not change the saved report. From the extracted bundle, run:

```sh
quarto render report.qmd --to typst --output report.pdf --no-execute
```

The report aliases local paths. Labels embedded inside original figure files are preserved unchanged and can still contain paths or sensitive text. The selected snapshot is a record excerpt, not a full database backup or an analysis replay package; nonfigure source files are referenced by name and hash rather than bundled. The manifest pins source evidence, not a byte-identical PDF across Quarto/font versions.

The first version supports preserved SVG, PNG and JPEG figures, up to 20 MB per figure, 100 MB total, and 50 selected states. SVGs containing embedded/linked content or external declarations are omitted with a warning. External references are never read by reporting. Recorded Markdown is escaped as display text; executable blocks and includes are not interpreted. Rendering uses a fixed Quarto argument list, disabled code execution and a controlled project configuration. One report renders at a time, with a three-minute timeout. Downloads require the viewer session token; download links last for the server session, while saved report files remain on disk. A renderer error leaves its local `render.log` for inspection.
