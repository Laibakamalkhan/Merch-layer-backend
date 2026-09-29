import json
def compact_json(value):
    return json.dumps(value, separators=(",",":"), ensure_ascii=False, default=str)
