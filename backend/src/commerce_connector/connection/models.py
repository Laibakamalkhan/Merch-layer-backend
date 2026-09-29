from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4
from commerce_connector.core.enums import ConnectionStatus

@dataclass(slots=True)
class Connection:
    name: str
    manifest_id: str
    manifest_path: str
    inputs: dict[str, Any]
    resources: list[str]
    connection_id: str = field(default_factory=lambda: f"con_{uuid4().hex[:12]}")
    tenant_id: str | None = None
    status: ConnectionStatus = ConnectionStatus.DRAFT
