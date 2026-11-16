"""Validated, immutable-by-copy proposal documents and canonical execution identity."""
import copy
import hashlib
import json
from ..store import ID, RecordError, text, names


def canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise RecordError("Workflow values must be finite JSON data") from exc


def identifier(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise RecordError("Invalid workflow identifier")
    return value


def document(value):
    if not isinstance(value, dict):
        raise RecordError("A workflow proposal must be an object")
    required = {"schemaVersion", "engine", "pipeline", "inputBindings", "configuration", "stages"}
    optional = {"contextStateIds", "limitations"}
    if not required <= value.keys() or value.keys() - required - optional:
        raise RecordError("Missing or unknown workflow proposal fields")
    if type(value["schemaVersion"]) is not int or value["schemaVersion"] != 1:
        raise RecordError("Unsupported workflow proposal schema")
    result = copy.deepcopy(value)
    canonical(result)
    for key, fields in (("engine", {"name", "version"}), ("pipeline", {"source", "revision", "contentDigest"})):
        obj = result[key]
        if not isinstance(obj, dict) or not fields <= obj.keys() or obj.keys() - fields - ({"name"} if key == "pipeline" else set()):
            raise RecordError(f"Invalid {key} identity")
        for field, entry in obj.items():
            text(entry, field, 20000, True)
    if not isinstance(result["configuration"], dict):
        raise RecordError("Configuration must be an object")
    for key in ("inputBindings", "stages", "contextStateIds", "limitations"):
        result.setdefault(key, [])
        if not isinstance(result[key], list):
            raise RecordError(f"{key} must be a list")
    if not result["inputBindings"] or not result["stages"]:
        raise RecordError("A proposal needs recorded inputs and stages")
    binding_names = set()
    for binding in result["inputBindings"]:
        if not isinstance(binding, dict) or set(binding) != {"name", "artifactId", "stateId"}:
            raise RecordError("Invalid input binding")
        for entry in binding.values():
            identifier(entry)
        if binding["name"] in binding_names:
            raise RecordError("Duplicate input binding name")
        binding_names.add(binding["name"])
    for entry in result["contextStateIds"]:
        identifier(entry)
    for entry in result["limitations"]:
        text(entry, "limitation", 20000, True)
    keys = set()
    # Require topological ordering; no inference or partial publication on invalid DAGs.
    for stage in result["stages"]:
        if not isinstance(stage, dict) or set(stage) - {"method"} != {"key", "title", "dependsOn", "expectedSummary", "expectedFiles", "mapping"}:
            raise RecordError("Invalid workflow stage")
        if "method" in stage:
            method = stage["method"]
            if not isinstance(method, dict) or not {"tool", "summary"} <= method.keys() or method.keys() - {"tool", "summary", "version"}:
                raise RecordError("Method needs a declared tool and short summary")
            for field, value in method.items():
                text(value, field, 1000, True)
        key = identifier(stage["key"])
        if key in keys or not isinstance(stage["dependsOn"], list) or any(not isinstance(i, str) for i in stage["dependsOn"]) or not set(stage["dependsOn"]) <= keys:
            raise RecordError("Stages must have unique keys and topologically ordered dependencies")
        if len(set(stage["dependsOn"])) != len(stage["dependsOn"]):
            raise RecordError("Duplicate stage dependency")
        text(stage["title"], "stage title", 120, True)
        text(stage["expectedSummary"], "expected result", 20000, True)
        names(stage["expectedFiles"])
        if not isinstance(stage["mapping"], dict) or not stage["mapping"]:
            raise RecordError("Each stage needs an explicit proposed evidence mapping")
        keys.add(key)
    return result


def execution_digest(spec):
    return hashlib.sha256(canonical(document(spec)).encode()).hexdigest()
