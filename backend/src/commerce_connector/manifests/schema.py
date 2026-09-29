from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from commerce_connector.core.enums import ProtocolType, ResponseFormat

class RetrySpec(BaseModel):
    max_attempts: int = Field(default=6, ge=1, le=20)
    base_delay_seconds: float = Field(default=0.5, gt=0)
    max_delay_seconds: float = Field(default=30.0, gt=0)
    retry_statuses: list[int] = Field(default_factory=lambda: [408,409,425,429,500,502,503,504])

class RateLimitSpec(BaseModel):
    requests_per_second: float | None = Field(default=None, gt=0)
    burst: int = Field(default=1, ge=1)
    respect_retry_after: bool = True

class CircuitBreakerSpec(BaseModel):
    enabled: bool = True
    failure_threshold: int = Field(default=8, ge=1)
    recovery_timeout_seconds: float = Field(default=30.0, gt=0)

class ConnectionFieldSpec(BaseModel):
    key: str
    label: str
    type: Literal["text","secret","url","choice"] = "text"
    target: str
    required: bool = True
    placeholder: str | None = None
    default: Any | None = None
    options: dict[str, Any] | None = None

class AuthSpec(BaseModel):
    model_config = ConfigDict(extra="allow")
    type: str = "none"

class PaginationSpec(BaseModel):
    model_config = ConfigDict(extra="allow")
    type: str = "none"
    max_pages: int = Field(default=100000, ge=1)
    records_path: str | None = None
    stop_on_empty: bool = True

    @model_validator(mode="after")
    def validate_strategy(self):
        data = self.model_dump()
        if self.type == "next_token" and not data.get("next_token_path"):
            raise ValueError("next_token pagination requires next_token_path")
        if self.type == "next_url" and not data.get("next_url_path"):
            raise ValueError("next_url pagination requires next_url_path")
        if self.type == "graphql_cursor":
            if not data.get("cursor_path") or not data.get("has_next_path"):
                raise ValueError("graphql_cursor requires cursor_path and has_next_path")
        return self

class ResponseSpecConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    format: ResponseFormat = ResponseFormat.AUTO
    records_path: str | None = None
    allow_graphql_partial_data: bool = False

class ResourceSpec(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str | None = None
    protocol: ProtocolType | None = None
    method: str = "GET"
    path: str
    headers: dict[str, str] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)
    body: Any | None = None
    graphql_query: str | None = None
    graphql_variables: dict[str, Any] = Field(default_factory=dict)
    content_type: str | None = None
    soap_action: str | None = None
    xml_body: str | None = None
    response: ResponseSpecConfig = Field(default_factory=ResponseSpecConfig)
    pagination: PaginationSpec = Field(default_factory=PaginationSpec)

class DiscoverySpec(BaseModel):
    openapi_url: str | None = None
    graphql_introspection: bool = False
    graphql_path: str | None = None
    wsdl_url: str | None = None

class PlatformManifest(BaseModel):
    model_config = ConfigDict(extra="allow")
    manifest_version: str = "1"
    id: str
    name: str
    platform: str
    protocol: ProtocolType
    base_url: str = ""
    default_headers: dict[str, str] = Field(default_factory=dict)
    default_params: dict[str, Any] = Field(default_factory=dict)
    connection_fields: list[ConnectionFieldSpec] = Field(default_factory=list)
    auth: AuthSpec = Field(default_factory=AuthSpec)
    retry: RetrySpec = Field(default_factory=RetrySpec)
    rate_limit: RateLimitSpec = Field(default_factory=RateLimitSpec)
    circuit_breaker: CircuitBreakerSpec = Field(default_factory=CircuitBreakerSpec)
    discovery: DiscoverySpec = Field(default_factory=DiscoverySpec)
    resources: dict[str, ResourceSpec] = Field(default_factory=dict)
