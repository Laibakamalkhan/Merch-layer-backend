from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import yaml

from commerce_connector.platform.db import PostgresGateway


def get_path(value: Any, path: str | None, *, parent: Any = None, context: dict[str, Any] | None = None) -> Any:
    if path is None:
        return None
    if not isinstance(path, str):
        return path
    if path.startswith("$parent."):
        value = parent
        path = path[len("$parent."):]
    elif path == "$parent":
        return parent
    elif path.startswith("$context."):
        value = context or {}
        path = path[len("$context."):]
    elif path.startswith("$literal:"):
        return path[len("$literal:"):]
    if path in ("", "."):
        return value
    current = value
    for part in path.split("."):
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit():
            idx = int(part)
            current = current[idx] if 0 <= idx < len(current) else None
        else:
            return None
    return current


def _json_if_needed(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, default=str)
    return value


class MappingRepository:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def load(self, platform: str, resource: str) -> dict[str, Any] | None:
        candidates = [
            self.root / platform / f"{resource}.yaml",
            self.root / platform.replace("-", "_") / f"{resource}.yaml",
        ]
        for path in candidates:
            if path.exists():
                data = yaml.safe_load(path.read_text(encoding="utf-8"))
                return data if isinstance(data, dict) else None
        return None


class SilverTransformer:
    """One transformation engine, platform/resource behavior in YAML mappings."""

    def __init__(self, db: PostgresGateway, mapping_root: str | Path):
        self.db = db
        self.mappings = MappingRepository(mapping_root)

    async def transform_records(
        self,
        *,
        tenant_id: str,
        connection_id: str,
        platform: str,
        resource: str,
        records: list[dict[str, Any]],
    ) -> dict[str, int]:
        mapping = self.mappings.load(platform, resource)
        if not mapping:
            return {"written": 0, "rejected": 0, "skipped": len(records)}
        written = 0
        rejected = 0
        for wrapper in records:
            try:
                count = await self._transform_one(
                    tenant_id=tenant_id,
                    connection_id=connection_id,
                    mapping=mapping,
                    wrapper=wrapper,
                )
                written += count
            except Exception:
                rejected += 1
        return {"written": written, "rejected": rejected, "skipped": 0}

    async def _transform_one(
        self,
        *,
        tenant_id: str,
        connection_id: str,
        mapping: dict[str, Any],
        wrapper: dict[str, Any],
    ) -> int:
        source = wrapper["record"]
        bronze_id = wrapper.get("bronze_id")
        record_hash = wrapper.get("record_hash")
        items: list[tuple[Any, Any]] = []
        explode = mapping.get("explode")
        if explode:
            exploded = get_path(source, explode) or []
            if isinstance(exploded, list):
                items = [(item, source) for item in exploded]
        else:
            items = [(source, None)]

        count = 0
        for item, parent in items:
            if not isinstance(item, dict):
                continue
            row: dict[str, Any] = {
                "tenant_id": tenant_id,
                "connection_id": connection_id,
            }
            for column, path in (mapping.get("fields") or {}).items():
                row[column] = get_path(item, path, parent=parent, context={"record_hash": record_hash})
            if mapping.get("include_raw_record_id", True):
                row["raw_record_id"] = bronze_id
            if "source_hash" in mapping.get("fields", {}) and row.get("source_hash") is None:
                row["source_hash"] = record_hash
            for column, value in (mapping.get("defaults") or {}).items():
                if row.get(column) is None:
                    row[column] = value

            # Resolve optional foreign keys from source IDs.
            for column, spec in (mapping.get("foreign_keys") or {}).items():
                source_id = get_path(item, spec.get("source_path"), parent=parent)
                row[column] = await asyncio.to_thread(
                    self.db.lookup_id,
                    spec["table"],
                    connection_id,
                    str(source_id) if source_id is not None else None,
                )

            required = mapping.get("required") or ["source_id"]
            if any(row.get(col) in (None, "") for col in required):
                raise ValueError(f"Missing required silver fields: {required}")

            # Remove null-only optional columns when requested.
            if mapping.get("drop_nulls", False):
                row = {k: v for k, v in row.items() if v is not None}
            await asyncio.to_thread(
                self.db.upsert_row,
                mapping["table"],
                row,
                mapping.get("conflict_columns") or ["connection_id", "source_id"],
            )
            count += 1

            # Child mappings are loaded from the same YAML object.
            for child in mapping.get("children") or []:
                await self._transform_child(
                    tenant_id=tenant_id,
                    connection_id=connection_id,
                    parent=item,
                    child=child,
                    bronze_id=bronze_id,
                    record_hash=record_hash,
                )
        return count

    async def _transform_child(
        self,
        *,
        tenant_id: str,
        connection_id: str,
        parent: dict[str, Any],
        child: dict[str, Any],
        bronze_id: Any,
        record_hash: str | None,
    ) -> None:
        items = get_path(parent, child.get("explode")) or []
        if not isinstance(items, list):
            return
        for item in items:
            if not isinstance(item, dict):
                continue
            row = {"tenant_id": tenant_id, "connection_id": connection_id}
            for column, path in (child.get("fields") or {}).items():
                row[column] = get_path(item, path, parent=parent, context={"record_hash": record_hash})
            if child.get("include_raw_record_id", True):
                row["raw_record_id"] = bronze_id
            for column, value in (child.get("defaults") or {}).items():
                if row.get(column) is None:
                    row[column] = value
            for column, spec in (child.get("foreign_keys") or {}).items():
                source_id = get_path(item, spec.get("source_path"), parent=parent)
                row[column] = await asyncio.to_thread(
                    self.db.lookup_id,
                    spec["table"],
                    connection_id,
                    str(source_id) if source_id is not None else None,
                )
            required = child.get("required") or []
            if any(row.get(col) in (None, "") for col in required):
                continue
            if child.get("drop_nulls", False):
                row = {k: v for k, v in row.items() if v is not None}
            await asyncio.to_thread(
                self.db.upsert_row,
                child["table"],
                row,
                child.get("conflict_columns") or ["connection_id", "source_id"],
            )
