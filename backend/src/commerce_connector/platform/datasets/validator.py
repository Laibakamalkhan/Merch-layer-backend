from __future__ import annotations

import re
from pathlib import Path
from typing import Any

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".json"}
ALLOWED_MIME_TYPES = {
    "text/csv",
    "text/plain",
    "application/csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/json",
    "application/octet-stream",
}

NUMERIC_PATTERN = re.compile(r"^[-+]?\d+(\.\d+)?([eE][-+]?\d+)?$")
FORMULA_CHARS = {"=", "+", "-", "@", "\t", "\r", "|"}


class SecurityValidationError(ValueError):
    """Raised when an uploaded file fails security or format constraints."""
    pass


def sanitize_csv_cell(value: Any) -> Any:
    """Sanitize potential spreadsheet formula injection while preserving valid numeric negative values."""
    if not isinstance(value, str):
        return value
    trimmed = value.strip()
    if not trimmed:
        return value

    # Valid negative or positive numeric numbers must be preserved as-is.
    if NUMERIC_PATTERN.match(trimmed):
        return value

    # If non-numeric text begins with a dangerous formula trigger, prefix with a single quote.
    if trimmed[0] in FORMULA_CHARS:
        return "'" + value
    return value


def validate_file_security(
    filename: str,
    content_type: str,
    data: bytes,
    *,
    max_bytes: int = 25 * 1024 * 1024,
) -> str:
    """Validate file extension, size, MIME type, and magic bytes.

    Returns the normalized file_type ('csv', 'xlsx', or 'json').
    """
    if not data:
        raise SecurityValidationError("File is empty")
    if len(data) > max_bytes:
        raise SecurityValidationError(f"File exceeds maximum allowed size of {max_bytes} bytes")

    ext = Path(filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise SecurityValidationError(f"Disallowed file extension '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}")

    # Inspect magic bytes and structure based on extension
    if ext == ".csv":
        # Check for null bytes (which indicate binary payloads rather than text CSV)
        prefix = data[:4096]
        if b"\x00" in prefix:
            raise SecurityValidationError("Binary null bytes detected in CSV payload")
        return "csv"

    if ext == ".xlsx":
        # Standard PKZip signature for OpenXML .xlsx files
        if not data.startswith(b"PK\x03\x04"):
            raise SecurityValidationError("Invalid XLSX file signature (must be a valid OpenXML spreadsheet)")
        # Reject macro-enabled files (.xlsm / embedded VBA)
        if b"vbaProject.bin" in data or filename.lower().endswith(".xlsm"):
            raise SecurityValidationError("Macro-enabled spreadsheets (.xlsm / VBA) are strictly prohibited")
        return "xlsx"

    if ext == ".json":
        # Must be valid UTF text starting with [ or {
        try:
            head = data[:256].decode("utf-8-sig", errors="strict").strip()
        except UnicodeDecodeError as exc:
            raise SecurityValidationError("JSON file must be valid UTF-8 text") from exc
        if not (head.startswith("{") or head.startswith("[")):
            raise SecurityValidationError("JSON file must start with an object '{' or array '['")
        return "json"

    raise SecurityValidationError(f"Unsupported file type: {ext}")
