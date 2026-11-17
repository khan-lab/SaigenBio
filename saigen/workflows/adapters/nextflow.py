"""Local Nextflow adapter. Static inspection never evaluates workflow code."""
import csv
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from ...records import RecordError
from .base import EngineInfo, LaunchSpec, EvidenceBatch


def source_files(source):
    root = Path(source).expanduser().resolve()
    if not root.is_dir() or not (root / 'main.nf').is_file():
        raise RecordError('Select a local pipeline directory containing main.nf')
    files = []
    for path in sorted(root.rglob('*')):
        if '.git' in path.relative_to(root).parts:
            continue
        if path.is_symlink():
            raise RecordError('Pipeline source must contain regular files, not symlinks')
        if path.is_file():
            files.append(path)
    return root, files


def source_digest(source):
    root, files = source_files(source)
    entries = [(str(p.relative_to(root)), hashlib.sha256(p.read_bytes()).hexdigest()) for p in files]
    return hashlib.sha256(json.dumps(entries, separators=(',', ':')).encode()).hexdigest()


class NextflowAdapter:
    def __init__(self):
        self.executable = shutil.which(os.environ.get('SAIGEN_NEXTFLOW', 'nextflow'))

    def discover(self):
        version = None
        if self.executable:
            try:
                result = subprocess.run([self.executable, '-version'], capture_output=True, text=True, timeout=30)
                match = re.search(r'\bversion ([\w.\-]+)', result.stdout + result.stderr)
                if result.returncode == 0 and match:
                    version = match[1]
            except (OSError, subprocess.TimeoutExpired):
                pass
        return EngineInfo('nextflow', version, version is not None, {
            'staticInspection': True, 'resolvedTaskPreview': False, 'localExecution': version is not None,
            'resume': False, 'multipleTasksPerStage': False, 'liveTaskEvidence': False})

    def inspect(self, source, configuration):
        root, files = source_files(source)
        return {'engine': asdict(self.discover()), 'pipeline': {'source': str(root),
            'revision': 'local-content', 'contentDigest': source_digest(root)},
            'files': [str(p.relative_to(root)) for p in files],
            'limitations': ['Static files only; no resolved task DAG.',
                'Execution evaluates pipeline code. Local executor and one task per mapped stage only.',
                'External includes, plugins, environments and remote dependencies are not captured by this source digest.']}

    def prepare(self, proposal):
        spec = proposal['spec']
        info = self.discover()
        if not info.available:
            raise RecordError('Nextflow is unavailable. Install Nextflow and compatible Java, or set SAIGEN_NEXTFLOW.')
        if info.version != spec['engine']['version']:
            raise RecordError('Nextflow version changed; inspect and approve a new proposal')
        if source_digest(spec['pipeline']['source']) != spec['pipeline']['contentDigest']:
            raise RecordError('Pipeline source changed; inspect and approve a new proposal')
        config = spec['configuration']
        if set(config) - {'parameters'} or not isinstance(config.get('parameters', {}), dict):
            raise RecordError('Local Nextflow configuration supports parameters only')
        if any(binding['name'] in config.get('parameters', {}) for binding in spec['inputBindings']):
            raise RecordError('An input parameter cannot also be supplied in parameters')
        processes = []
        for stage in spec['stages']:
            mapping = stage['mapping']
            if set(mapping) != {'process'} or not isinstance(mapping['process'], str) or not mapping['process']:
                raise RecordError('Map each stage to exactly one qualified Nextflow process name')
            processes.append(mapping['process'])
            if not stage['expectedFiles']:
                raise RecordError('Each stage needs at least one declared output')
            for name in stage['expectedFiles']:
                path = Path(name)
                if not name or path.is_absolute() or '..' in path.parts:
                    raise RecordError('Stage outputs must be relative paths inside a task work directory')
        if len(set(processes)) != len(processes):
            raise RecordError('Each process must map to exactly one stage')
        return LaunchSpec((self.executable, 'run', 'pipeline/main.nf', '-ansi-log', 'false',
            '-work-dir', 'work', '-params-file', 'params.json', '-with-trace', 'trace.tsv'), '', ('trace.tsv',))

    def stage(self, proposal, folder, parameters, launch):
        """Materialize this adapter's launch files without executing scientific code."""
        shutil.copytree(proposal['spec']['pipeline']['source'], folder / 'pipeline', ignore=shutil.ignore_patterns('.git'))
        if source_digest(folder / 'pipeline') != proposal['spec']['pipeline']['contentDigest']:
            raise RecordError('Pipeline changed during staging; create a new proposal')
        (folder / 'params.json').write_text(json.dumps(parameters))
        config = folder / 'saigen.config'
        config.write_text("process.executor = 'local'\ntrace.fields = 'task_id,process,status,exit,attempt,workdir'\ntrace.raw = true\n")
        configs = [str(p) for p in [folder / 'pipeline' / 'nextflow.config', config] if p.exists()]
        if any(',' in p for p in configs):
            raise RecordError('Nextflow config paths containing commas are unsupported')
        return LaunchSpec((launch.argv[0], '-C', ','.join(configs), *launch.argv[1:]), str(folder), launch.evidence_locations)

    def collect(self, run_reference, cursor=None):
        path = Path(run_reference) / 'trace.tsv'
        rows = []
        if path.is_file():
            with path.open() as stream:
                for row in csv.DictReader(stream, delimiter='\t'):
                    if row.get('task_id') and row.get('process') and row.get('status'):
                        rows.append(row)
        return EvidenceBatch(tuple(rows), None)
