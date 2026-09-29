from enum import Enum

class ProtocolType(str, Enum):
    REST = "rest"
    GRAPHQL = "graphql"
    SOAP = "soap"
    HTTP = "http"
    FILE = "file"
    BULK = "bulk"

class ResponseFormat(str, Enum):
    AUTO = "auto"
    JSON = "json"
    XML = "xml"
    CSV = "csv"
    NDJSON = "ndjson"
    TEXT = "text"
    BYTES = "bytes"

class ConnectionStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    DISABLED = "disabled"
    FAILED = "failed"
