from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class TenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=160)
    timezone: str = Field(default="UTC", min_length=1, max_length=100)


class ConnectionCreate(BaseModel):
    tenant_id: UUID
    platform_code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    base_url: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    enabled_resources: list[str] | None = None
    secrets: dict[str, str] = Field(default_factory=dict, description="Stored in Supabase Vault; never returned by the API.")

    @field_validator("secrets")
    @classmethod
    def reject_blank_secrets(cls, value: dict[str, str]) -> dict[str, str]:
        return {k: v for k, v in value.items() if isinstance(v, str) and v.strip()}


class ConnectionResourceUpdate(BaseModel):
    enabled: bool | None = None
    sync_mode: Literal["full", "incremental", "webhook", "bulk"] | None = None




class ConnectionUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    base_url: str | None = Field(default=None, max_length=500)
    config: dict[str, Any] = Field(default_factory=dict)
    secrets: dict[str, str] = Field(default_factory=dict)


class CredentialUpsert(BaseModel):
    tenant_id: UUID
    secrets: dict[str, str] = Field(min_length=1)

    @field_validator("secrets")
    @classmethod
    def clean_secrets(cls, value: dict[str, str]) -> dict[str, str]:
        cleaned = {k: v for k, v in value.items() if isinstance(v, str) and v.strip()}
        if not cleaned:
            raise ValueError("At least one non-empty secret is required")
        return cleaned


class SyncRequest(BaseModel):
    tenant_id: UUID
    connection_ids: list[UUID] = Field(min_length=1)
    rebuild_rag_after_sync: bool = False


class AIQuestionRequest(BaseModel):
    tenant_id: UUID
    question: str = Field(min_length=2, max_length=8000)


class RAGRebuildRequest(BaseModel):
    tenant_id: UUID


class DataQuery(BaseModel):
    tenant_id: UUID
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
    connection_id: UUID | None = None


class APIMessage(BaseModel):
    message: str


class TableQueryRequest(BaseModel):
    tenant_id: UUID | None = None
    user_id: UUID | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
    order_by: str | None = None
    order_dir: Literal["asc", "desc"] = "desc"
    include_large_fields: bool = False


class AuthSignupRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=200)
    display_name: str | None = Field(default=None, max_length=200)


class AuthResendRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class AuthLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=200)


class AuthRefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=10)


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=200)
    avatar_url: str | None = Field(default=None, max_length=2000)
    timezone: str | None = Field(default=None, max_length=100)


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=160)
    timezone: str = Field(default="UTC", min_length=1, max_length=100)


class TaskCreate(BaseModel):
    tenant_id: UUID
    title: str | None = Field(default=None, max_length=200)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskUpdate(BaseModel):
    tenant_id: UUID
    title: str | None = Field(default=None, max_length=200)
    archived: bool | None = None
    pinned: bool | None = None


class MessageCreate(BaseModel):
    tenant_id: UUID
    role: Literal["user", "assistant"] = "user"
    content: str = Field(min_length=1, max_length=100000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AIQuestionRequestV2(BaseModel):
    tenant_id: UUID
    question: str = Field(min_length=2, max_length=8000)
    conversation_id: UUID | None = None
    reasoning: bool = False
    model_id: str = Field(default="merchlayer-2.0", max_length=100)
    file_ids: list[UUID] = Field(default_factory=list, max_length=20)
    include_debug: bool = False


class PlanChangeRequest(BaseModel):
    tenant_id: UUID
    plan_code: str = Field(min_length=1, max_length=50)


class UpgradeIntentRequest(BaseModel):
    tenant_id: UUID
    plan_code: str = Field(min_length=1, max_length=50)
    return_url: str | None = Field(default=None, max_length=2000)


class ConversationMessageCreate(BaseModel):
    """Body for POST /conversations/{id}/messages and /conversations/{id}/stream.

    There is deliberately no ``role`` field: the server always stores the sender
    as ``user`` and the AI reply as ``assistant``, so a client cannot forge an
    assistant message.
    """

    tenant_id: UUID
    content: str = Field(min_length=2, max_length=8000, description="The user's question.")
    reasoning: bool = False
    model_id: str = Field(default="merchlayer-2.0", max_length=100)
    file_ids: list[UUID] = Field(default_factory=list, max_length=20)
    include_debug: bool = False


class DatasetIngestRequest(BaseModel):
    tenant_id: UUID
    target_entity: Literal["orders", "order_items", "products", "customers"]
    column_mappings: dict[str, str] = Field(min_length=1, description="Map source headers to canonical field names")
    natural_key_column: str | None = Field(default=None, description="Source column to use as unique natural identifier")
    rebuild_rag_after_sync: bool = False


class DatasetItemResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    connection_id: UUID | None = None
    filename: str
    file_type: str
    byte_size: int
    checksum_sha256: str
    status: str
    has_validation_errors: bool = False
    detected_entity: str | None = None
    profile_summary: dict[str, Any] = Field(default_factory=dict)
    mapping_config: dict[str, Any] = Field(default_factory=dict)
    quality_summary: dict[str, Any] = Field(default_factory=dict)
    row_count: int = 0
    error_message: str | None = None
    created_at: Any
    updated_at: Any