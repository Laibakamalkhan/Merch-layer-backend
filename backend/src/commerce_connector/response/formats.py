from commerce_connector.core.enums import ResponseFormat
def detect_format(content_type):
    c = content_type.lower()
    if "json" in c:return ResponseFormat.JSON
    if "xml" in c or "soap" in c:return ResponseFormat.XML
    if "csv" in c:return ResponseFormat.CSV
    if "ndjson" in c or "x-ndjson" in c:return ResponseFormat.NDJSON
    if c.startswith("text/"):return ResponseFormat.TEXT
    return ResponseFormat.BYTES
