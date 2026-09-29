import csv, io
def parse_csv(raw): return list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
