from __future__ import annotations

import pytest
from commerce_connector.platform.datasets.profiler import profile_dataset


def test_profile_dataset_orders_detection():
    rows = [
        {"order_id": "1001", "order_date": "2026-09-01", "total_amount": "150.50", "currency": "USD"},
        {"order_id": "1002", "order_date": "2026-09-02", "total_amount": "200.00", "currency": "USD"},
        {"order_id": "1003", "order_date": "2026-09-03", "total_amount": "75.25", "currency": "USD"},
    ]
    result = profile_dataset(rows)
    assert result.row_count == 3
    assert result.detected_entity == "orders"
    assert result.candidate_natural_key == "order_id"
    assert not result.has_validation_errors
    assert "revenue" in result.available_metrics
    assert "orders_count" in result.available_metrics
    assert result.suggested_mappings.get("total_amount") == "gross_amount"
    assert result.suggested_mappings.get("order_date") == "source_created_at"


def test_profile_dataset_duplicate_natural_key_detection():
    rows = [
        {"order_id": "1001", "amount": "50.00", "date": "2026-09-01"},
        {"order_id": "1001", "amount": "75.00", "date": "2026-09-01"},  # Duplicate key!
        {"order_id": "1002", "amount": "100.00", "date": "2026-09-02"},
    ]
    result = profile_dataset(rows)
    assert result.has_validation_errors is True
    assert len(result.validation_issues) > 0
    issue = result.validation_issues[0]
    assert issue["type"] == "duplicate_natural_key"
    assert "1001" in issue["message"]


def test_profile_dataset_products_detection():
    rows = [
        {"sku": "SKU-A", "product_name": "T-Shirt", "price": "29.99", "category": "Apparel"},
        {"sku": "SKU-B", "product_name": "Jeans", "price": "59.99", "category": "Apparel"},
    ]
    result = profile_dataset(rows)
    assert result.detected_entity == "products"
    assert result.candidate_natural_key == "sku"
    assert result.suggested_mappings.get("product_name") == "title"


def test_profile_dataset_customers_detection():
    rows = [
        {"customer_id": "C1", "email": "alice@example.com", "first_name": "Alice", "total_spent": "500.00"},
        {"customer_id": "C2", "email": "bob@example.com", "first_name": "Bob", "total_spent": "250.00"},
    ]
    result = profile_dataset(rows)
    assert result.detected_entity == "customers"
    assert result.candidate_natural_key == "customer_id"
    assert result.suggested_mappings.get("email") == "email"


def test_profile_dataset_empty_rows():
    result = profile_dataset([])
    assert result.row_count == 0
    assert result.has_validation_errors is True
