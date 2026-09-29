from copy import deepcopy
def get_dotted(data, path, default=None):
    current = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current

def set_dotted(data, path, value):
    parts = path.split(".")
    current = data
    for part in parts[:-1]:
        if not isinstance(current.get(part), dict):
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value

def apply_connection_inputs(manifest, inputs):
    runtime = deepcopy(manifest)
    for field in runtime.get("connection_fields", []):
        key = field["key"]
        if key not in inputs:
            continue
        value = inputs[key]
        if field.get("type") == "choice":
            value = (field.get("options") or {}).get(str(value), value)
        set_dotted(runtime, field["target"], value)
    return runtime
