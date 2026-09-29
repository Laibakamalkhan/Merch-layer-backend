from commerce_connector.core.enums import ResponseFormat
from commerce_connector.core.exceptions import ProtocolError
from commerce_connector.core.models import ResponseSpec
from .csv_parser import parse_csv
from .formats import detect_format
from .ndjson_parser import parse_ndjson
from .xml_parser import parse_xml

def parse_response(response, definition):
    fmt = definition.format
    if fmt == ResponseFormat.AUTO:
        fmt = detect_format(response.headers.get("content-type",""))
        if fmt == ResponseFormat.BYTES:
            try: response.json(); fmt = ResponseFormat.JSON
            except Exception: pass
    raw = response.content
    if fmt == ResponseFormat.JSON:
        data = response.json()
        if isinstance(data,dict) and data.get("errors") and not definition.allow_graphql_partial_data:
            raise ProtocolError(f"API/GraphQL errors: {data['errors']}")
    elif fmt == ResponseFormat.XML:data = parse_xml(raw)
    elif fmt == ResponseFormat.CSV:data = parse_csv(raw)
    elif fmt == ResponseFormat.NDJSON:data = parse_ndjson(raw)
    elif fmt == ResponseFormat.TEXT:data = response.text
    else:data = raw
    return ResponseSpec(
        status_code=response.status_code, url=str(response.url),
        headers={k.lower():v for k,v in response.headers.items()},
        data=data, raw_bytes=raw,
    )
