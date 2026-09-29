from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from .enums import ProtocolType

@dataclass(slots=True)
class RequestSpec:
    method: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)
    json_body: Any | None = None
    content: bytes | str | None = None

    def clone(self):
        return RequestSpec(
            method=self.method,
            url=self.url,
            headers=dict(self.headers),
            params=dict(self.params),
            json_body=dict(self.json_body) if isinstance(self.json_body, dict) else self.json_body,
            content=self.content,
        )

@dataclass(slots=True)
class ResponseSpec:
    status_code: int
    url: str
    headers: dict[str, str]
    data: Any
    raw_bytes: bytes

@dataclass(slots=True)
class PaginationDecision:
    has_next: bool
    state: dict[str, Any] = field(default_factory=dict)

@dataclass(slots=True)
class ConnectorPage:
    resource: str
    page_number: int
    request: RequestSpec
    response: ResponseSpec
    records: Any
    record_count: int | None
    checkpoint: dict[str, Any] | None = None

@dataclass(slots=True)
class DiscoveryResult:
    protocol: ProtocolType | None
    platform: str | None
    operations: list[dict[str, Any]]
    resources: list[dict[str, Any]]
    pagination: dict[str, Any] | None = None
    confidence: float = 0.0
    raw_schema: Any | None = None
