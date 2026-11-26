"""Inventory and fingerprint local workflow source trees."""

import hashlib
import json

from ...records import RecordError


def source_files(root, excluded=('.git',)):
    files = []
    for path in sorted(root.rglob('*')):
        if any(part in excluded for part in path.relative_to(root).parts):
            continue
        if path.is_symlink():
            raise RecordError('Pipeline source must contain regular files, not symlinks')
        if path.is_file():
            files.append(path)
    return files


def source_digest(root, excluded=('.git',)):
    entries = [(str(p.relative_to(root)), hashlib.sha256(p.read_bytes()).hexdigest())
               for p in source_files(root, excluded)]
    return hashlib.sha256(json.dumps(entries, separators=(',', ':')).encode()).hexdigest()
