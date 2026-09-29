from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from commerce_connector.manifests.repository import ManifestRepository
from commerce_connector.platform.db import PostgresGateway


def set_nested(target: dict[str, Any], dotted_path: str, value: Any) -> None:
    parts = dotted_path.split(".")
    current = target
    for part in parts[:-1]:
        child = current.get(part)
        if not isinstance(child, dict):
            child = {}
            current[part] = child
        current = child
    current[parts[-1]] = value


class RuntimeManifestFactory:
    def __init__(self, db: PostgresGateway, manifest_root: str | Path):
        self.db = db
        self.repository = ManifestRepository(manifest_root)

    def _find_manifest(self, connection: dict[str, Any]):
        manifest_key = connection.get("manifest_key")
        if manifest_key:
            try:
                return self.repository.get_by_id(manifest_key).manifest
            except KeyError:
                pass
        for record in self.repository.discover():
            if record.manifest.platform == connection["platform_code"]:
                return record.manifest
        raise KeyError(
            f"No local manifest for platform={connection['platform_code']} manifest_key={manifest_key}"
        )

    def build(self, connection_id: str) -> dict[str, Any]:
        connection = self.db.get_connection(connection_id)
        manifest = deepcopy(self._find_manifest(connection).model_dump(mode="json"))
        config = connection.get("config") or {}

        if connection.get("base_url"):
            manifest["base_url"] = connection["base_url"]

        for field in manifest.get("connection_fields", []):
            key = field["key"]
            target = field["target"]
            if field.get("type") == "secret":
                try:
                    value = self.db.get_secret(connection_id, key)
                except Exception:
                    if field.get("required", True):
                        raise
                    value = None  # optional secret jo save hi nahi hua
            else:
                value = config.get(key)
                if target == "base_url" and connection.get("base_url"):
                    value = connection["base_url"]
            if value is not None and value != "":
                # Some API query parameters (for example Amazon MarketplaceIds)
                # are list-valued even though the UI collects one value.
                if target.endswith("MarketplaceIds") and not isinstance(value, list):
                    value = [value]
                set_nested(manifest, target, value)

        return manifest
