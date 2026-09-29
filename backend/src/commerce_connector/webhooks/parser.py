import json
def parse_json_event(payload): return json.loads(payload.decode('utf-8'))
