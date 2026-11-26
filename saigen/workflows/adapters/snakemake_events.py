"""Snakemake logger staged alongside each attempt and loaded by its engine."""

import json
import os

from snakemake_interface_logger_plugins.base import LogHandlerBase
from snakemake_interface_logger_plugins.common import LogEvent


_EVENT_FIELDS = {
    LogEvent.WORKFLOW_STARTED: ('workflow_id',),
    LogEvent.JOB_INFO: ('jobid', 'rule_name', 'output', 'shellcmd', 'wildcards'),
    LogEvent.JOB_FINISHED: ('job_id',),
    LogEvent.JOB_ERROR: ('jobid', 'rule_name', 'output', 'shellcmd'),
}


class LogHandler(LogHandlerBase):
    writes_to_stream = False
    writes_to_file = True
    has_filter = True
    has_formatter = False
    needs_rulegraph = False

    def __post_init__(self):
        self.baseFilename = os.environ['SAIGEN_SNAKEMAKE_EVENTS']

    def emit(self, record):
        event = getattr(record, 'event', None)
        # Snakemake subprocesses also load the plugin. The supervisor alone
        # observes the lifecycle of all jobs in the approved attempt.
        if event not in _EVENT_FIELDS or os.getpid() != os.getsid(0):
            return
        evidence = {field: getattr(record, field, None) for field in _EVENT_FIELDS[event]}
        evidence['event'] = event.name
        with open(self.baseFilename, 'a', encoding='utf-8') as stream:
            stream.write(json.dumps(evidence, default=str) + '\n')
