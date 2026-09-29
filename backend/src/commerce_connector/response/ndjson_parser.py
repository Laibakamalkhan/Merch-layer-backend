import json
def parse_ndjson(raw):
    return [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
