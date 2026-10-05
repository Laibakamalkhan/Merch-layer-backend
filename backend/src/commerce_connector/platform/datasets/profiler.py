from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

# Known synonyms for canonical commerce fields
CANONICAL_SYNONYMS = {
    "orders": {
        "source_id": {"order_id", "orderid", "id", "order_number", "ordernumber", "invoice_no", "invoiceno", "invoice_number", "transaction_id", "transactionid", "order_no"},
        "order_number": {"order_number", "ordernumber", "order_no", "invoice_no", "invoiceno", "name", "number"},
        "gross_amount": {"total", "order_total", "ordertotal", "total_amount", "totalamount", "gross", "gross_amount", "gross_sales", "amount", "revenue", "price"},
        "net_amount": {"net", "net_amount", "netamount", "net_sales", "subtotal", "subtotal_amount"},
        "discount_amount": {"discount", "discounts", "discount_amount", "total_discount", "coupon_discount"},
        "shipping_amount": {"shipping", "shipping_amount", "shipping_fee", "delivery_fee", "freight"},
        "tax_amount": {"tax", "taxes", "tax_amount", "total_tax", "vat", "gst"},
        "refunded_amount": {"refund", "refunds", "refunded_amount", "total_refund"},
        "currency_code": {"currency", "currency_code", "currencycode", "curr"},
        "financial_status": {"financial_status", "payment_status", "status", "paid_status"},
        "fulfillment_status": {"fulfillment_status", "shipping_status", "delivery_status"},
        "source_created_at": {"date", "order_date", "orderdate", "created_at", "createdat", "timestamp", "purchase_date", "datetime"},
        "processed_at": {"processed_at", "processedat", "paid_at", "fulfillment_date"},
    },
    "products": {
        "source_id": {"product_id", "productid", "id", "sku", "item_id", "itemid", "product_code"},
        "title": {"title", "product_name", "productname", "name", "item_name", "itemname", "product_title"},
        "product_type": {"product_type", "type", "category", "product_category"},
        "vendor": {"vendor", "brand", "manufacturer", "supplier"},
        "status": {"status", "is_active", "state"},
        "description": {"description", "body", "details", "desc"},
        "source_created_at": {"created_at", "date", "createdat"},
    },
    "customers": {
        "source_id": {"customer_id", "customerid", "id", "user_id", "userid", "client_id"},
        "email": {"email", "customer_email", "email_address", "mail"},
        "phone": {"phone", "customer_phone", "mobile", "telephone"},
        "first_name": {"first_name", "firstname", "first", "fname"},
        "last_name": {"last_name", "lastname", "last", "lname"},
        "display_name": {"name", "display_name", "customer_name", "full_name", "fullname"},
        "orders_count": {"orders_count", "orders", "total_orders", "number_of_orders"},
        "total_spent": {"total_spent", "total_spend", "amount_spent", "ltv", "lifetime_value"},
    },
}

DATE_REGEX = re.compile(r"^\d{4}[-/.]\d{1,2}[-/.]\d{1,2}(?:[ T]\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)?$")
DECIMAL_REGEX = re.compile(r"^[-+]?\$?\s*\(?\d+(?:,\d{3})*(?:\.\d+)?\)?$")
INT_REGEX = re.compile(r"^[-+]?\d+$")
BOOL_VALUES = {"true", "false", "1", "0", "yes", "no", "y", "n"}


@dataclass
class ColumnProfile:
    name: str
    inferred_type: str
    null_count: int
    total_count: int
    sample_values: list[Any]
    suggested_field: str | None = None
    confidence: float = 0.0


@dataclass
class DatasetProfileResult:
    row_count: int
    detected_entity: str
    columns: list[ColumnProfile]
    suggested_mappings: dict[str, str]
    candidate_natural_key: str | None = None
    has_validation_errors: bool = False
    validation_issues: list[dict[str, Any]] = field(default_factory=list)
    available_metrics: list[str] = field(default_factory=list)
    unavailable_metrics: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _clean_header(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", name.strip().lower()).strip("_")
    return cleaned or "col"


def _infer_value_type(val: Any) -> str:
    if val is None:
        return "null"
    if isinstance(val, (bool,)):
        return "boolean"
    if isinstance(val, (int,)):
        return "integer"
    if isinstance(val, (float,)):
        return "decimal"
    s = str(val).strip()
    if not s:
        return "null"
    if s.lower() in BOOL_VALUES:
        return "boolean"
    if INT_REGEX.match(s):
        return "integer"
    if DECIMAL_REGEX.match(s):
        return "decimal"
    if DATE_REGEX.match(s):
        return "date"
    return "string"


def profile_dataset(records: Iterable[dict[str, Any]], *, max_sample_rows: int = 5000) -> DatasetProfileResult:
    """Analyze row dictionaries and compute column statistics, entity suggestions, and key validation."""
    rows: list[dict[str, Any]] = []
    for idx, r in enumerate(records):
        rows.append(r)
        if idx + 1 >= max_sample_rows:
            break

    if not rows:
        return DatasetProfileResult(
            row_count=0,
            detected_entity="orders",
            columns=[],
            suggested_mappings={},
            has_validation_errors=True,
            validation_issues=[{"type": "empty_dataset", "message": "Dataset contains no rows"}],
        )

    all_keys: list[str] = []
    for r in rows:
        for k in r.keys():
            if k not in all_keys:
                all_keys.append(k)

    column_profiles: list[ColumnProfile] = []
    key_values_map: dict[str, list[Any]] = {k: [] for k in all_keys}

    for col in all_keys:
        null_count = 0
        samples: list[Any] = []
        type_counts: dict[str, int] = {}

        for r in rows:
            v = r.get(col)
            if v is None or str(v).strip() == "":
                null_count += 1
            else:
                v_type = _infer_value_type(v)
                type_counts[v_type] = type_counts.get(v_type, 0) + 1
                key_values_map[col].append(str(v).strip())
                if len(samples) < 5 and v not in samples:
                    samples.append(v)

        # Primary inferred type is the dominant non-null type
        inferred_type = "string"
        if type_counts:
            # Prefer decimal over integer if both present
            if "decimal" in type_counts or "integer" in type_counts:
                inferred_type = "decimal" if "decimal" in type_counts else "integer"
            else:
                inferred_type = max(type_counts.items(), key=lambda x: x[1])[0]

        column_profiles.append(
            ColumnProfile(
                name=col,
                inferred_type=inferred_type,
                null_count=null_count,
                total_count=len(rows),
                sample_values=samples,
            )
        )

    # Entity detection scores
    scores: dict[str, float] = {"orders": 0.0, "products": 0.0, "customers": 0.0}
    clean_cols_map = {_clean_header(c): c for c in all_keys}

    for entity, syn_map in CANONICAL_SYNONYMS.items():
        for field_name, synonyms in syn_map.items():
            for clean_col in clean_cols_map:
                if clean_col in synonyms or any(s in clean_col for s in synonyms):
                    scores[entity] += 1.0

    detected_entity = max(scores.items(), key=lambda x: x[1])[0]

    # Map candidate fields
    suggested_mappings: dict[str, str] = {}
    syn_map = CANONICAL_SYNONYMS[detected_entity]

    for prof in column_profiles:
        clean_col = _clean_header(prof.name)
        best_field = None
        best_conf = 0.0
        for canonical_field, synonyms in syn_map.items():
            if clean_col in synonyms:
                best_field = canonical_field
                best_conf = 0.95
                break
            elif any(s in clean_col for s in synonyms):
                if 0.75 > best_conf:
                    best_field = canonical_field
                    best_conf = 0.75

        if best_field and best_field not in suggested_mappings.values():
            prof.suggested_field = best_field
            prof.confidence = best_conf
            suggested_mappings[prof.name] = best_field

    # Natural Key Detection & Duplicate Check
    candidate_key = None
    validation_issues: list[dict[str, Any]] = []
    has_validation_errors = False

    id_col = None
    for prof in column_profiles:
        if prof.suggested_field == "source_id" or _clean_header(prof.name) in {"order_id", "id", "sku", "customer_id", "invoice_no"}:
            id_col = prof.name
            break

    if id_col:
        candidate_key = id_col
        values = key_values_map.get(id_col, [])
        duplicates = set()
        seen = set()
        for val in values:
            if val in seen:
                duplicates.add(val)
            seen.add(val)

        if duplicates:
            has_validation_errors = True
            validation_issues.append({
                "type": "duplicate_natural_key",
                "column": id_col,
                "message": f"Duplicate natural identifier detected in column '{id_col}': {len(duplicates)} duplicates found (e.g. {list(duplicates)[:3]}).",
                "sample_duplicates": list(duplicates)[:5],
            })

    # Available/Unavailable metrics calculation
    available: list[str] = []
    unavailable: list[str] = []

    if detected_entity == "orders":
        if "gross_amount" in suggested_mappings.values() or "net_amount" in suggested_mappings.values():
            available.extend(["revenue", "daily_sales"])
            if "source_id" in suggested_mappings.values() or candidate_key:
                available.extend(["orders_count", "aov"])
        else:
            unavailable.extend(["revenue", "aov"])
        unavailable.extend(["inventory_levels", "fulfillments"])

    return DatasetProfileResult(
        row_count=len(rows),
        detected_entity=detected_entity,
        columns=column_profiles,
        suggested_mappings=suggested_mappings,
        candidate_natural_key=candidate_key,
        has_validation_errors=has_validation_errors,
        validation_issues=validation_issues,
        available_metrics=available,
        unavailable_metrics=unavailable,
    )
