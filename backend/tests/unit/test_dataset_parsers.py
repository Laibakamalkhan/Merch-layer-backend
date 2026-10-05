import io
import json
import pytest

from commerce_connector.platform.datasets.validator import (
    SecurityValidationError,
    sanitize_csv_cell,
    validate_file_security,
)
from commerce_connector.platform.datasets.parsers import (
    parse_dataset_stream,
    parse_csv_stream,
    parse_xlsx_stream,
    parse_json_stream,
)


def test_sanitize_csv_cell_preserves_negative_numbers():
    assert sanitize_csv_cell("-150.50") == "-150.50"
    assert sanitize_csv_cell("-5") == "-5"
    assert sanitize_csv_cell("+42.0") == "+42.0"
    assert sanitize_csv_cell(123) == 123
    assert sanitize_csv_cell(-45.67) == -45.67


def test_sanitize_csv_cell_neutralizes_formulas():
    assert sanitize_csv_cell("=cmd|' /C calc'!A0") == "'=cmd|' /C calc'!A0"
    assert sanitize_csv_cell("@SUM(1,2)") == "'@SUM(1,2)"
    assert sanitize_csv_cell("+cmd|") == "'+cmd|"
    assert sanitize_csv_cell("Normal Text") == "Normal Text"


def test_validate_file_security():
    # Valid CSV
    assert validate_file_security("test.csv", "text/csv", b"col1,col2\n1,2") == "csv"
    # Valid JSON
    assert validate_file_security("test.json", "application/json", b'[{"id": 1}]') == "json"

    # Disallowed extension
    with pytest.raises(SecurityValidationError, match="Disallowed file extension"):
        validate_file_security("bad.exe", "application/octet-stream", b"MZ...")

    # Empty file
    with pytest.raises(SecurityValidationError, match="File is empty"):
        validate_file_security("empty.csv", "text/csv", b"")

    # Binary in CSV
    with pytest.raises(SecurityValidationError, match="Binary null bytes detected"):
        validate_file_security("corrupt.csv", "text/csv", b"col1,col2\x00\x00bad")

    # Macro xlsm rejection by extension
    with pytest.raises(SecurityValidationError, match="Disallowed file extension"):
        validate_file_security("sheet.xlsm", "application/vnd.ms-excel", b"PK\x03\x04...")

    # Macro payload inside .xlsx
    with pytest.raises(SecurityValidationError, match="Macro-enabled"):
        validate_file_security("sheet.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", b"PK\x03\x04...vbaProject.bin...")


def test_csv_parser_variations():
    # Semicolon delimiter with quotes and multiline
    csv_data = 'order_id;amount;notes\n1001;150.50;"Line 1\nLine 2"\n1002;-25.00;Refund'.encode("utf-8")
    rows = list(parse_csv_stream(csv_data))
    assert len(rows) == 2
    assert rows[0]["order_id"] == "1001"
    assert rows[0]["amount"] == "150.50"
    assert rows[0]["notes"] == "Line 1\nLine 2"
    assert rows[1]["amount"] == "-25.00"


def test_xlsx_parser():
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Orders"
    ws.append(["order_id", "total", "customer"])
    ws.append(["101", 99.95, "Alice"])
    ws.append(["102", -10.00, "Bob"])

    buf = io.BytesIO()
    wb.save(buf)
    xlsx_data = buf.getvalue()

    rows = list(parse_xlsx_stream(xlsx_data))
    assert len(rows) == 2
    assert rows[0]["order_id"] == "101"
    assert rows[0]["total"] == 99.95
    assert rows[1]["total"] == -10.00


def test_json_parser():
    # Array format
    json_array = b'[{"order_id": "J1", "amount": 50}, {"order_id": "J2", "amount": 75}]'
    rows = list(parse_json_stream(json_array))
    assert len(rows) == 2
    assert rows[0]["order_id"] == "J1"

    # Wrapped object format
    json_wrapped = b'{"orders": [{"order_id": "W1", "amount": 120}]}'
    rows = list(parse_json_stream(json_wrapped))
    assert len(rows) == 1
    assert rows[0]["order_id"] == "W1"
