"""Static inspection and local execution of approved Snakemake workflows."""

from dataclasses import asdict
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from ...records import RecordError
from .base import EngineInfo, EvidenceBatch, LaunchSpec
from .source import source_files, source_digest


_ENTRYPOINTS = ('Snakefile', 'workflow/Snakefile')
_EXCLUDED = ('.git', '.saigen', '.snakemake')
_EVENTS = 'snakemake-events.jsonl'


def pipeline_source(source):
    root = Path(source).expanduser().resolve()
    entrypoint = None
    if root.is_file() and root.name == 'Snakefile':
        entrypoint = 'workflow/Snakefile' if root.parent.name == 'workflow' else 'Snakefile'
        root = root.parent.parent if entrypoint.startswith('workflow/') else root.parent
    elif root.is_dir():
        entrypoint = next((name for name in _ENTRYPOINTS if (root / name).is_file()), None)
        if entrypoint == 'Snakefile' and root.name == 'workflow':
            return pipeline_source(root / entrypoint)
    if not entrypoint:
        raise RecordError('Select a local Snakefile or a directory containing Snakefile or workflow/Snakefile')
    return root, entrypoint


def relative_path(value):
    return (
        isinstance(value, str) and bool(value) and not value.startswith('-')
        and bool(Path(value).parts) and not Path(value).is_absolute()
        and '..' not in Path(value).parts and '\0' not in value
    )


def events(folder):
    path = folder / _EVENTS
    if path.is_file():
        with path.open(encoding='utf-8') as stream:
            for line in stream:
                # An interrupted write may leave one incomplete final record.
                if line.endswith('\n'):
                    yield json.loads(line)


class SnakemakeAdapter:
    display_name = 'Snakemake'
    mapping_key = 'rule'
    evidence_source = 'Snakemake job events'
    work_directory = 'pipeline'
    task_script = None

    def __init__(self):
        self.executable = shutil.which(os.environ.get('SAIGEN_SNAKEMAKE', 'snakemake'))

    def discover(self):
        version = None
        if self.executable:
            try:
                result = subprocess.run([self.executable, '--version'], capture_output=True, text=True, timeout=30)
                if result.returncode == 0 and re.fullmatch(r'\d+\.\d+\.\d+', result.stdout.strip()):
                    version = result.stdout.strip()
            except (OSError, subprocess.TimeoutExpired):
                pass
        return EngineInfo('snakemake', version, version is not None, {
            'staticInspection': True, 'resolvedTaskPreview': False,
            'localExecution': bool(version and version.startswith('9.27.')),
            'resume': False, 'multipleTasksPerStage': False, 'liveTaskEvidence': False,
        })

    def inspect(self, source, configuration):
        root, entrypoint = pipeline_source(source)
        return {'engine': asdict(self.discover()), 'pipeline': {
            'source': str(root / entrypoint), 'revision': 'local-content', 'name': root.name,
            'contentDigest': source_digest(root, _EXCLUDED),
        }, 'files': [str(path.relative_to(root)) for path in source_files(root, _EXCLUDED)],
            'limitations': ['Static files only. No resolved job DAG.',
                'Local Snakemake 9.27.x execution with one job per mapped rule.',
                'External dependencies and environments are outside the source digest.']}

    def prepare(self, proposal):
        spec = proposal['spec']
        info = self.discover()
        if not info.capabilities['localExecution']:
            raise RecordError('Local execution requires Snakemake 9.27.x on PATH or via SAIGEN_SNAKEMAKE')
        if info.version != spec['engine']['version']:
            raise RecordError('Snakemake version changed; inspect and approve a new proposal')
        root, entrypoint = pipeline_source(spec['pipeline']['source'])
        if source_digest(root, _EXCLUDED) != spec['pipeline']['contentDigest']:
            raise RecordError('Pipeline source changed; inspect and approve a new proposal')
        config = spec['configuration']
        targets = config.get('targets')
        cores = config.get('cores', 1)
        params = config.get('parameters', {})
        if set(config) - {'targets', 'cores', 'parameters'} or not isinstance(params, dict):
            raise RecordError('Local Snakemake configuration supports targets, cores and parameters')
        if type(cores) is not int or cores < 1:
            raise RecordError('Snakemake cores must be a positive integer')
        if not isinstance(targets, list) or not targets or not all(relative_path(t) for t in targets):
            raise RecordError('List at least one explicit relative Snakemake target')
        if any(binding['name'] in params for binding in spec['inputBindings']):
            raise RecordError('An input config key cannot also be supplied in parameters')
        rules = set()
        for stage in spec['stages']:
            mapping = stage['mapping']
            rule = mapping.get('rule')
            if set(mapping) != {'rule'} or not isinstance(rule, str) or not rule.isidentifier() or rule in rules:
                raise RecordError('Map each stage to a distinct Snakemake rule name')
            rules.add(rule)
            if not stage['expectedFiles'] or not all(relative_path(p) for p in stage['expectedFiles']):
                raise RecordError('Each stage needs relative expected output paths inside the workflow directory')
        return LaunchSpec((self.executable, '--snakefile', entrypoint, '--cores', str(cores),
            '--executor', 'local', '--scheduler', 'greedy', '--profile', 'none', '--workflow-profile', 'none', '--forceall',
            '--notemp', '--printshellcmds', '--logger', 'saigen', '--configfile', '../params.json',
            '--', *targets), '', (_EVENTS,))

    def stage(self, proposal, folder, parameters, launch):
        root, _ = pipeline_source(proposal['spec']['pipeline']['source'])
        shutil.copytree(root, folder / 'pipeline', ignore=shutil.ignore_patterns(*_EXCLUDED))
        if source_digest(folder / 'pipeline', _EXCLUDED) != proposal['spec']['pipeline']['contentDigest']:
            raise RecordError('Pipeline changed during staging; create a new proposal')
        (folder / 'params.json').write_text(json.dumps(parameters))
        logger = folder / 'snakemake_logger_plugin_saigen' / '__init__.py'
        logger.parent.mkdir()
        shutil.copyfile(Path(__file__).with_name('snakemake_events.py'), logger)
        return LaunchSpec(launch.argv, str(folder / 'pipeline'), launch.evidence_locations,
            environment_files=('params.json', str(logger.relative_to(folder))), env={
                'PYTHONPATH': os.pathsep.join(filter(None, (str(folder), os.environ.get('PYTHONPATH')))),
                'SAIGEN_SNAKEMAKE_EVENTS': str(folder / _EVENTS),
            })

    def collect(self, run_reference, cursor=None):
        rows = []
        jobs = {}
        for event in events(Path(run_reference)):
            kind = event['event']
            job = event.get('jobid') if kind != 'JOB_FINISHED' else event.get('job_id')
            rule = event.get('rule_name')
            if kind == 'JOB_INFO' and job is not None and rule:
                row = {'task_id': str(job), 'rule': rule, 'status': 'STARTED',
                    'declaredOutputs': event.get('output') or [], 'command': event.get('shellcmd'),
                    'wildcards': event.get('wildcards')}
                jobs[job] = row
                rows.append(row)
            elif kind == 'JOB_ERROR' and job in jobs:
                jobs[job]['status'] = 'FAILED'
            elif kind == 'JOB_FINISHED' and job in jobs and jobs[job]['status'] == 'STARTED':
                jobs[job].update(status='COMPLETED', exit='0')
        return EvidenceBatch(tuple(rows), None)

    def run_identity(self, folder):
        return next((event['workflow_id'] for event in events(folder)
            if event['event'] == 'WORKFLOW_STARTED' and event.get('workflow_id')), None)
