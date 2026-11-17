"""Bundled report presentation. Receives prepared evidence; never reads analysis files."""
from __future__ import annotations
import hashlib
import json
import re
from .records import RecordError

DEFAULT_TEMPLATE = "analysis-notebook"
TEMPLATES = {
    "results-summary": {"name": "Results summary", "description": "Figures, tables and recorded explanations with brief method context.", "version": 1,
        "sections": ["overview", "previews", "method_summary"], "scripts": "none"},
    "analysis-notebook": {"name": "Analysis notebook", "description": "Results alongside recorded methods, scripts and decisions.", "version": 1,
        "sections": ["overview", "method_summary", "scripts", "commands", "execution", "previews"], "scripts": "excerpts-or-full"},
    "reproducibility-appendix": {"name": "Reproducibility appendix", "description": "Commands, declared files, software information and artifact references.", "version": 1,
        "sections": ["overview", "method_summary", "inventory", "environment", "commands", "scripts", "execution", "previews"], "scripts": "full"},
}
LABELS = {"overview":"Recorded explanation", "previews":"Saved figures and table excerpts", "method_summary":"Method", "scripts":"Preserved scripts", "commands":"Commands", "execution":"Execution notes", "inventory":"Inputs, outputs and artifact references", "environment":"Software and execution information"}


def template_definition(ident):
    if not isinstance(ident, str) or ident not in TEMPLATES:
        raise RecordError("Unknown report template")
    definition = {"id": ident, **TEMPLATES[ident]}
    definition["sha256"] = hashlib.sha256(json.dumps(definition, sort_keys=True).encode()).hexdigest()
    return definition


def literal(value):
    # Escape all Markdown syntax, including executable fences, raw blocks and links.
    return re.sub(r'([!"#$%&\'()*+,\-./:;<=>?@\[\\\]^_`{|}~])', r'\\\1', str(value or ""))


def code_cell(value, language=""):
    # Plain language fences are display-only; never use Quarto executable braces.
    value = str(value)
    fence = "`" * max(3, max((len(m.group()) + 1 for m in re.finditer(r"`+", value)), default=3))
    return [fence + language, value, fence, ""]


def table_cell(value):
    return literal(value).replace("\n", " ").replace("\r", " ")



def compose(model, template):
    body = ['---', 'title: ' + json.dumps(model['project']), 'subtitle: ' + json.dumps(template['name']),
            'format:', '  typst:', '    papersize: a4', '    fontsize: 10pt', '    code-overflow: wrap',
            '    margin:', '      x: 20mm', '      y: 18mm', 'execute:', '  enabled: false', '---', '',
            'Selected analysis · Revision ' + str(model['revision']), '',
            'Presentation order only; no analysis is rerun. Evidence is limited to what was recorded.', '']
    outline=[]
    for index, state in enumerate(model['states'],1):
        body += ['# ' + str(index) + '. ' + literal(state['title']), '']
        visible=[]
        for key in template['sections']:
            lines=state[key]
            if key == 'scripts' and template['scripts']=='excerpts-or-full' and state['excerpts']:
                lines=state['excerpts']
            if not lines:
                continue
            label = "Planned result and prerequisites" if key=="overview" and state["status"]=="planned" else LABELS[key]
            visible.append(label)
            if key != 'overview':
                body += ['## ' + label, '']
            body += lines
        # Failed/unknown statuses and missing evidence must remain visible even in compact reports.
        if 'execution' not in template['sections'] and state['execution']:
            visible.append(LABELS['execution'])
            body += ['## '+LABELS['execution'], ''] + state['execution']
        outline.append({'title':state['title'], 'status':state['status'], 'sections':visible})
    if model['warnings']:
        body += ['# Evidence warnings', '']
        body += ['- '+literal(w) for w in model['warnings']]
        body += ['']
    body += ['The source bundle contains the selected snapshot, artifact references and hashes. Nonfigure source files are referenced rather than bundled. An omitted script is not missing evidence. This document is not a full backup or an environment replay package.', '']
    return '\n'.join(body), outline
