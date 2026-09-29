from dataclasses import dataclass, field
from typing import Any

@dataclass(slots=True)
class ConnectorContext:
    connection_id: str
    connection_name: str
    platform: str
    resource: str | None = None
    tenant_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
