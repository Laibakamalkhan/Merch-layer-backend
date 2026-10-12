from __future__ import annotations

import json
import re
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterable, Sequence
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


class PostgresGateway:
    """Thin gateway over the finalized Supabase Postgres schemas.

    The service role / direct DB connection is used by the backend prototype.
    Frontend clients never issue SQL directly; all access comes through FastAPI/services and this gateway.
    """

    def __init__(self, database_url: str):
        self.database_url = database_url.strip()
        if not self.database_url:
            raise ValueError("database_url is required")
        # SPEED FIX: pehle har ek query par nayi DB connection banti thi (remote Supabase par har baar 1-2 second).
        # Sync mein hazaron queries hoti hain, isliye 10+ minute lagte thay. Ab connections ek pool se dobara use hote hain.
        self._pool = None
        try:
            from psycopg_pool import ConnectionPool

            self._pool = ConnectionPool(
                self.database_url,
                min_size=1,
                max_size=10,
                kwargs={"row_factory": dict_row, "prepare_threshold": None},  # None = Supabase pooler ke saath bhi theek
                open=False,
            )
            self._pool.open()
        except ImportError:
            self._pool = None  # psycopg_pool install nahi: purana (slow) tareeqa chalega

    @contextmanager
    def connection(self):
        if self._pool is not None:
            with self._pool.connection() as conn:
                yield conn
            return
        with psycopg.connect(self.database_url, row_factory=dict_row) as conn:
            yield conn

    def ping(self) -> dict[str, Any]:
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute("select current_database() as database, now() as server_time")
            return cur.fetchone()

    def fetch_all(self, sql: str, params: Sequence[Any] | dict[str, Any] | None = None) -> list[dict[str, Any]]:
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())

    def fetch_one(self, sql: str, params: Sequence[Any] | dict[str, Any] | None = None) -> dict[str, Any] | None:
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()

    def execute(self, sql: str, params: Sequence[Any] | dict[str, Any] | None = None) -> int:
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.rowcount

    # ------------------------------------------------------------------
    # IAM / tenant helpers
    # ------------------------------------------------------------------
    def list_tenants(self) -> list[dict[str, Any]]:
        return self.fetch_all(
            "select id, name, slug, timezone, created_at from iam.tenants order by created_at desc"
        )

    def create_tenant(self, name: str, slug: str, timezone: str = "UTC") -> dict[str, Any]:
        slug = re.sub(r"[^a-z0-9-]+", "-", slug.lower()).strip("-")
        if not slug:
            raise ValueError("A valid tenant slug is required")
        row = self.fetch_one(
            """
            insert into iam.tenants(name, slug, timezone)
            values (%s, %s, %s)
            on conflict (slug) do update set
              name = excluded.name,
              timezone = excluded.timezone,
              updated_at = now()
            returning id, name, slug, timezone, created_at
            """,
            (name, slug, timezone),
        )
        assert row is not None
        return row

    # ------------------------------------------------------------------
    # Platform / connection catalog
    # ------------------------------------------------------------------
    def list_platforms(self) -> list[dict[str, Any]]:
        return self.fetch_all(
            """
            select id, code, name, protocol::text as protocol, status::text as status,
                   manifest_key, category, connection_fields, capabilities, metadata
            from control.platforms
            where status::text = 'active'
            order by name
            """
        )

    def list_connections(self, tenant_id: str | UUID) -> list[dict[str, Any]]:
        return self.fetch_all(
            """
            select c.id, c.tenant_id, c.platform_id, c.platform_version_id, c.name,
                   c.base_url, c.external_account_id, c.status::text as status,
                   c.config, c.metadata, c.last_tested_at, c.last_synced_at,
                   p.code as platform_code, p.name as platform_name,
                   p.protocol::text as protocol, p.manifest_key
            from control.connections c
            join control.platforms p on p.id = c.platform_id
            where c.tenant_id = %s
            order by c.created_at desc
            """,
            (tenant_id,),
        )

    def get_connection(self, connection_id: str | UUID) -> dict[str, Any]:
        row = self.fetch_one(
            """
            select c.id, c.tenant_id, c.platform_id, c.platform_version_id, c.name,
                   c.base_url, c.external_account_id, c.status::text as status,
                   c.config, c.metadata, c.last_tested_at, c.last_synced_at,
                   p.code as platform_code, p.name as platform_name,
                   p.protocol::text as protocol, p.manifest_key
            from control.connections c
            join control.platforms p on p.id = c.platform_id
            where c.id = %s
            """,
            (connection_id,),
        )
        if not row:
            raise KeyError(f"Unknown connection {connection_id}")
        return row

    def get_platform_by_code(self, platform_code: str) -> dict[str, Any]:
        row = self.fetch_one(
            """
            select id, code, name, protocol::text as protocol, manifest_key,
                   connection_fields, capabilities, metadata
            from control.platforms
            where code = %s
            """,
            (platform_code,),
        )
        if not row:
            raise KeyError(f"Platform not found: {platform_code}")
        return row

    def create_connection(
        self,
        *,
        tenant_id: str | UUID,
        platform_code: str,
        name: str,
        base_url: str | None,
        config: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        enabled_resources: list[str] | None = None,
    ) -> dict[str, Any]:
        platform = self.get_platform_by_code(platform_code)
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                insert into control.connections(
                    tenant_id, platform_id, name, base_url, status, config, metadata
                )
                values (%s, %s, %s, %s, 'draft', %s::jsonb, %s::jsonb)
                returning id, tenant_id, platform_id, name, base_url, status::text as status,
                          config, metadata
                """,
                (
                    tenant_id,
                    platform["id"],
                    name,
                    base_url,
                    json.dumps(config or {}),
                    json.dumps(metadata or {}),
                ),
            )
            connection = cur.fetchone()
            cur.execute("select app.initialize_connection_resources(%s) as initialized", (connection["id"],))
            if enabled_resources is not None:
                cur.execute(
                    """
                    update control.connection_resources
                    set enabled = (resource_key = any(%s::text[])), updated_at = now()
                    where connection_id = %s
                    """,
                    (enabled_resources, connection["id"]),
                )
            return connection

    def set_connection_status(self, connection_id: str | UUID, status: str) -> None:
        self.execute(
            "update control.connections set status = %s::app.connection_status, updated_at = now() where id = %s",
            (status, connection_id),
        )

    def find_connection_by_name(self, tenant_id: str | UUID, name: str) -> dict[str, Any] | None:
        """Isi tenant mein isi naam ka connection dhoondta hai (duplicate key error se bachne ke liye)."""
        return self.fetch_one(
            """
            select c.id, c.tenant_id, c.name, p.code as platform_code
            from control.connections c
            join control.platforms p on p.id = c.platform_id
            where c.tenant_id = %s and c.name = %s
            """,
            (tenant_id, name),
        )

    def update_connection_basics(
        self,
        connection_id: str | UUID,
        name: str | None,
        base_url: str | None,
        config: dict[str, Any] | None = None,
    ) -> None:
        # config purane config ke saath merge hota hai (jsonb ||), replace nahi.
        self.execute(
            """
            update control.connections
            set name = coalesce(%s, name),
                base_url = coalesce(%s, base_url),
                config = coalesce(config, '{}'::jsonb) || %s::jsonb,
                updated_at = now()
            where id = %s
            """,
            (name, base_url, json.dumps(config or {}), connection_id),
        )

    def mark_connection_test(self, connection_id: str | UUID, ok: bool) -> None:
        status = "active" if ok else "error"
        self.execute(
            """
            update control.connections
            set status = %s::app.connection_status,
                last_test_status = %s::app.connection_status,
                last_tested_at = now(), updated_at = now()
            where id = %s
            """,
            (status, status, connection_id),
        )

    def get_connection_resources(self, connection_id: str | UUID, enabled_only: bool = True) -> list[dict[str, Any]]:
        sql = """
            select id, tenant_id, connection_id, platform_resource_id, resource_key,
                   canonical_resource, enabled, sync_mode::text as sync_mode,
                   permission_status::text as permission_status, config,
                   last_success_at, last_error_at, last_error_code
            from control.connection_resources
            where connection_id = %s
        """
        if enabled_only:
            sql += " and enabled = true"
        sql += " order by resource_key"
        return self.fetch_all(sql, (connection_id,))

    def set_resource_permission(self, connection_id: str | UUID, resource_key: str, status: str, error_code: str | None = None) -> None:
        self.execute(
            """
            update control.connection_resources
            set permission_status = %s::app.permission_status,
                last_error_at = case when %s::text is null then last_error_at else now() end,
                last_error_code = %s::text,
                updated_at = now()
            where connection_id = %s and resource_key = %s
            """,
            (status, error_code, error_code, connection_id, resource_key),
        )

    # ------------------------------------------------------------------
    # Vault helpers
    # ------------------------------------------------------------------
    def store_secret(self, tenant_id: str | UUID, connection_id: str | UUID, secret_key: str, value: str) -> UUID:
        row = self.fetch_one(
            "select app.store_connection_secret(%s,%s,%s,%s) as secret_id",
            (tenant_id, connection_id, secret_key, value),
        )
        return row["secret_id"]

    def get_secret(self, connection_id: str | UUID, secret_key: str) -> str | None:
        row = self.fetch_one(
            "select app.get_connection_secret(%s,%s) as value",
            (connection_id, secret_key),
        )
        return row["value"] if row else None

    # ------------------------------------------------------------------
    # Ingestion jobs / runs
    # ------------------------------------------------------------------
    def create_job(self, tenant_id: str | UUID, connection_ids: list[str | UUID], trigger_type: str = "manual") -> dict[str, Any]:
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                insert into ingestion.sync_jobs(
                    tenant_id, trigger_type, sync_mode, status, total_connections
                ) values (%s, %s::app.trigger_type, 'incremental', 'queued', %s)
                returning *
                """,
                (tenant_id, trigger_type, len(connection_ids)),
            )
            job = cur.fetchone()
            for cid in connection_ids:
                resources = self.get_connection_resources(cid, enabled_only=True)
                selected = [r["resource_key"] for r in resources]
                cur.execute(
                    """
                    insert into ingestion.sync_job_connections(
                        tenant_id, job_id, connection_id, status, selected_resources
                    ) values (%s,%s,%s,'queued',%s::text[])
                    on conflict (job_id, connection_id) do update set
                      selected_resources = excluded.selected_resources,
                      status = 'queued', updated_at = now()
                    """,
                    (tenant_id, job["id"], cid, selected),
                )
            return job

    def start_job(self, job_id: str | UUID) -> None:
        self.execute(
            "update ingestion.sync_jobs set status='running', started_at=coalesce(started_at,now()), updated_at=now() where id=%s",
            (job_id,),
        )

    def create_run(
        self,
        *,
        tenant_id: str | UUID,
        job_id: str | UUID,
        connection_id: str | UUID,
        resource_key: str,
        canonical_resource: str | None,
        sync_mode: str = "incremental",
    ) -> dict[str, Any]:
        job_connection = self.fetch_one(
            "select id from ingestion.sync_job_connections where job_id=%s and connection_id=%s",
            (job_id, connection_id),
        )
        row = self.fetch_one(
            """
            insert into ingestion.sync_runs(
              tenant_id, job_id, job_connection_id, connection_id, resource_key,
              canonical_resource, sync_mode, status, started_at
            ) values (%s,%s,%s,%s,%s,%s,%s::app.sync_mode,'running',now())
            returning *
            """,
            (
                tenant_id,
                job_id,
                job_connection["id"] if job_connection else None,
                connection_id,
                resource_key,
                canonical_resource,
                sync_mode,
            ),
        )
        assert row is not None
        return row

    def finish_run(
        self,
        run_id: str | UUID,
        *,
        status: str,
        records_fetched: int = 0,
        records_written: int = 0,
        records_rejected: int = 0,
        pages_fetched: int = 0,
        bytes_fetched: int = 0,
        checkpoint_after: dict[str, Any] | None = None,
        error_summary: dict[str, Any] | None = None,
    ) -> None:
        self.execute(
            """
            update ingestion.sync_runs
            set status=%s::app.run_status,
                records_fetched=%s, records_written=%s, records_rejected=%s,
                pages_fetched=%s, bytes_fetched=%s,
                checkpoint_after=%s::jsonb,
                error_count=%s,
                error_summary=%s::jsonb,
                finished_at=now(), updated_at=now()
            where id=%s
            """,
            (
                status,
                records_fetched,
                records_written,
                records_rejected,
                pages_fetched,
                bytes_fetched,
                json.dumps(checkpoint_after) if checkpoint_after is not None else None,
                1 if error_summary else 0,
                json.dumps(error_summary or {}),
                run_id,
            ),
        )

    def finalize_job(self, job_id: str | UUID) -> str:
        row = self.fetch_one("select app.finalize_job_status(%s)::text as status", (job_id,))
        return row["status"]

    def get_checkpoint(self, connection_id: str | UUID, resource_key: str) -> dict[str, Any] | None:
        row = self.fetch_one(
            "select checkpoint from ingestion.checkpoints where connection_id=%s and resource_key=%s",
            (connection_id, resource_key),
        )
        return row["checkpoint"] if row else None

    def upsert_checkpoint(
        self,
        tenant_id: str | UUID,
        connection_id: str | UUID,
        resource_key: str,
        checkpoint: dict[str, Any],
        run_id: str | UUID,
    ) -> None:
        self.execute(
            "select app.upsert_checkpoint(%s,%s,%s,%s::jsonb,null,%s)",
            (tenant_id, connection_id, resource_key, json.dumps(checkpoint), run_id),
        )

    # ------------------------------------------------------------------
    # Bronze
    # ------------------------------------------------------------------
    def insert_raw_object(
        self,
        *,
        tenant_id: str | UUID,
        job_id: str | UUID,
        run_id: str | UUID,
        connection_id: str | UUID,
        resource_key: str,
        object_path: str,
        content_type: str,
        content_encoding: str | None,
        compression: str | None,
        checksum_sha256: str,
        byte_size: int,
        record_count: int,
        page_number: int,
        source_cursor: str | None,
        source_metadata: dict[str, Any] | None = None,
        bucket_id: str = "commerce-bronze",
    ) -> dict[str, Any]:
        row = self.fetch_one(
            """
            insert into bronze.raw_objects(
              tenant_id,job_id,run_id,connection_id,resource_key,bucket_id,object_path,
              content_type,content_encoding,compression,checksum_sha256,byte_size,
              record_count,page_number,source_cursor,source_metadata
            ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
            on conflict (bucket_id, object_path) do update set
              checksum_sha256=excluded.checksum_sha256,
              byte_size=excluded.byte_size,
              record_count=excluded.record_count,
              source_metadata=excluded.source_metadata
            returning *
            """,
            (
                tenant_id, job_id, run_id, connection_id, resource_key, bucket_id,
                object_path, content_type, content_encoding, compression, checksum_sha256,
                byte_size, record_count, page_number, source_cursor,
                json.dumps(source_metadata or {}),
            ),
        )
        assert row is not None
        return row

    def insert_extraction_page(
        self,
        *,
        tenant_id: str | UUID,
        run_id: str | UUID,
        connection_id: str | UUID,
        resource_key: str,
        page_number: int,
        raw_object_id: str | UUID | None,
        record_count: int,
        http_status: int | None,
        elapsed_ms: int | None = None,
        cursor_in: str | None = None,
        cursor_out: str | None = None,
        response_metadata: dict[str, Any] | None = None,
    ) -> None:
        self.execute(
            """
            insert into ingestion.extraction_pages(
              tenant_id,run_id,connection_id,resource_key,page_number,cursor_in,cursor_out,
              raw_object_id,record_count,http_status,elapsed_ms,response_metadata
            ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
            on conflict (run_id,page_number) do update set
              cursor_out=excluded.cursor_out,
              raw_object_id=excluded.raw_object_id,
              record_count=excluded.record_count,
              http_status=excluded.http_status,
              elapsed_ms=excluded.elapsed_ms,
              response_metadata=excluded.response_metadata
            """,
            (
                tenant_id, run_id, connection_id, resource_key, page_number,
                cursor_in, cursor_out, raw_object_id, record_count, http_status,
                elapsed_ms, json.dumps(response_metadata or {}),
            ),
        )

    def insert_bronze_record(
        self,
        *,
        tenant_id: str | UUID,
        job_id: str | UUID,
        run_id: str | UUID,
        connection_id: str | UUID,
        resource_key: str,
        source_record_id: str | None,
        source_updated_at: Any | None,
        record_hash: str,
        payload: Any,
        raw_object_id: str | UUID | None,
    ) -> Any:
        row = self.fetch_one(
            """
            insert into bronze.records(
              tenant_id,job_id,run_id,connection_id,resource_key,source_record_id,
              source_updated_at,record_hash,payload,raw_object_id
            ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)
            on conflict do nothing
            returning id
            """,
            (
                tenant_id, job_id, run_id, connection_id, resource_key,
                source_record_id, source_updated_at, record_hash,
                json.dumps(payload, default=str), raw_object_id,
            ),
        )
        if row:
            return row["id"]
        existing = self.fetch_one(
            """
            select id from bronze.records
            where connection_id=%s and resource_key=%s
              and coalesce(source_record_id,'')=coalesce(%s,'')
              and record_hash=%s
            order by ingested_at desc nulls last
            limit 1
            """,
            (connection_id, resource_key, source_record_id, record_hash),
        )
        return existing["id"] if existing else None

    # ------------------------------------------------------------------
    # Generic Silver helpers
    # ------------------------------------------------------------------
    def upsert_row(self, table: str, row: dict[str, Any], conflict_columns: list[str]) -> None:
        if not re.fullmatch(r"[a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*", table):
            raise ValueError(f"Unsafe table name: {table}")
        columns = list(row)
        if not columns:
            return
        for column in columns:
            if not re.fullmatch(r"[a-z_][a-z0-9_]*", column):
                raise ValueError(f"Unsafe column name: {column}")
        placeholders = ",".join(["%s"] * len(columns))
        updates = [c for c in columns if c not in set(conflict_columns) and c != "id"]
        update_sql = ",".join(f"{c}=excluded.{c}" for c in updates)
        sql = (
            f"insert into {table} ({','.join(columns)}) values ({placeholders}) "
            f"on conflict ({','.join(conflict_columns)}) do update set {update_sql}"
        )
        values = [Jsonb(v) if isinstance(v, dict) else v for v in row.values()]
        self.execute(sql, values)

    def lookup_id(self, table: str, connection_id: str | UUID, source_id: str | None) -> Any | None:
        if not source_id:
            return None
        if not re.fullmatch(r"silver\.[a-z_][a-z0-9_]*", table):
            raise ValueError("Only silver lookups are allowed")
        row = self.fetch_one(
            f"select id from {table} where connection_id=%s and source_id=%s limit 1",
            (connection_id, source_id),
        )
        return row["id"] if row else None

    # ------------------------------------------------------------------
    # AI / RAG helpers
    # ------------------------------------------------------------------
    def execute_readonly_query(self, sql: str, tenant_id: str | UUID, timeout_ms: int = 10000) -> list[dict[str, Any]]:
        # SQLGuard converts :tenant_id into %(tenant_id)s.
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute("set transaction read only")
            # PostgreSQL does not allow bind parameters in SET LOCAL utility
            # statements. set_config(..., true) applies the value locally to
            # the current transaction while still keeping the timeout value
            # parameterized (and therefore safe from SQL injection).
            cur.execute(
                "select set_config('statement_timeout', %s, true)",
                (f"{int(timeout_ms)}ms",),
            )
            cur.execute(sql, {"tenant_id": str(tenant_id)})
            return list(cur.fetchall())

    def get_data_coverage(self, tenant_id: str | UUID) -> dict[str, Any]:
        sql = (
            "select min(metric_date) as first_date, max(metric_date) as last_date, "
            "count(*) as days_with_data "
            "from gold.daily_sales where tenant_id = %s"
        )
        try:
            row = self.fetch_one(sql, (str(tenant_id),))
            if not row:
                return {"first_date": None, "last_date": None, "days_with_data": 0}
            return {
                "first_date": row.get("first_date"),
                "last_date": row.get("last_date"),
                "days_with_data": int(row.get("days_with_data") or 0),
            }
        except Exception as exc:
            logger.warning("Failed to fetch data coverage for tenant_id=%s: %s", tenant_id, exc)
            return {"first_date": None, "last_date": None, "days_with_data": 0}

    def create_query_run(
        self,
        tenant_id: str | UUID,
        prompt: str,
        model_name: str,
        *,
        conversation_id: str | UUID | None = None,
        user_id: str | UUID | None = None,
    ) -> dict[str, Any]:
        row = self.fetch_one(
            """
            insert into ai.query_runs(tenant_id,user_id,conversation_id,user_prompt,status,model_name)
            values (%s,%s,%s,%s,'planned',%s)
            returning *
            """,
            (tenant_id, user_id, conversation_id, prompt, model_name),
        )
        assert row is not None
        return row

    def update_query_run(
        self,
        query_run_id: str | UUID,
        *,
        status: str,
        route: str | None = None,
        intent: dict[str, Any] | None = None,
        selected_context: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> None:
        self.execute(
            """
            update ai.query_runs
            set status=%s::app.ai_query_status,
                route=coalesce(
                    (
                        select e.enumlabel::app.ai_route
                        from pg_catalog.pg_enum e
                        where e.enumtypid = 'app.ai_route'::regtype
                          and e.enumlabel = %s
                    ),
                    route
                ),
                intent=coalesce(%s::jsonb,intent),
                selected_context=coalesce(%s::jsonb,selected_context),
                error_message=%s,
                finished_at=case when %s in ('completed','failed','blocked') then now() else finished_at end
            where id=%s
            """,
            (
                status,
                route,
                json.dumps(intent) if intent is not None else None,
                json.dumps(selected_context) if selected_context is not None else None,
                error_message,
                status,
                query_run_id,
            ),
        )

    def save_generated_query(
        self,
        *,
        tenant_id: str | UUID,
        query_run_id: str | UUID,
        sql_text: str,
        validation_status: str,
        blocked_reason: str | None = None,
        execution_ms: int | None = None,
        row_count: int | None = None,
        result_preview: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        row = self.fetch_one(
            """
            insert into ai.generated_queries(
              tenant_id,query_run_id,sql_text,validation_status,blocked_reason,
              execution_ms,row_count,result_preview,executed_at
            ) values (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,
                      case when %s='approved' then now() else null end)
            returning *
            """,
            (
                tenant_id, query_run_id, sql_text, validation_status, blocked_reason,
                execution_ms, row_count,
                json.dumps(result_preview or [], default=str), validation_status,
            ),
        )
        assert row is not None
        return row

    def save_dashboard_spec(
        self,
        tenant_id: str | UUID,
        query_run_id: str | UUID,
        title: str,
        description: str,
        spec: dict[str, Any],
    ) -> dict[str, Any]:
        row = self.fetch_one(
            """
            insert into ai.dashboard_specs(tenant_id,user_id,query_run_id,title,description,spec,status)
            values (%s,(select user_id from ai.query_runs where id=%s),%s,%s,%s,%s::jsonb,'draft')
            returning *
            """,
            (tenant_id, query_run_id, query_run_id, title, description, json.dumps(spec, default=str)),
        )
        assert row is not None
        return row

    def list_dashboards(self, tenant_id: str | UUID, limit: int = 50) -> list[dict[str, Any]]:
        return self.fetch_all(
            """
            select id,title,description,spec,status::text as status,version,created_at
            from ai.dashboard_specs
            where tenant_id=%s
            order by created_at desc
            limit %s
            """,
            (tenant_id, limit),
        )

    def replace_semantic_documents(self, tenant_id: str | UUID, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "delete from ai.documents where tenant_id=%s and source_type in ('schema','metric','connection')",
                (tenant_id,),
            )
            result = []
            for doc in documents:
                cur.execute(
                    """
                    insert into ai.documents(tenant_id,source_type,source_ref,title,content,content_hash,metadata)
                    values (%s,%s,%s,%s,%s,%s,%s::jsonb)
                    returning *
                    """,
                    (
                        tenant_id,
                        doc["source_type"],
                        doc.get("source_ref"),
                        doc["title"],
                        doc["content"],
                        doc.get("content_hash"),
                        json.dumps(doc.get("metadata") or {}),
                    ),
                )
                result.append(cur.fetchone())
            return result

    def replace_document_chunks(
        self,
        document_id: str | UUID,
        tenant_id: str | UUID,
        chunks: list[dict[str, Any]],
    ) -> None:
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute("delete from ai.document_chunks where document_id=%s", (document_id,))
            for chunk in chunks:
                cur.execute(
                    """
                    insert into ai.document_chunks(
                      tenant_id,document_id,chunk_index,content,token_count,content_hash,
                      embedding,embedding_model,metadata
                    ) values (%s,%s,%s,%s,%s,%s,%s::extensions.vector,%s,%s::jsonb)
                    """,
                    (
                        tenant_id,
                        document_id,
                        chunk["chunk_index"],
                        chunk["content"],
                        chunk.get("token_count"),
                        chunk.get("content_hash"),
                        chunk["embedding"],
                        chunk.get("embedding_model"),
                        json.dumps(chunk.get("metadata") or {}),
                    ),
                )

    def replace_semantic_documents_with_chunks(
        self,
        tenant_id: str | UUID,
        documents: list[dict[str, Any]],
        *,
        embedding_model: str,
        output_dimensions: int,
    ) -> dict[str, int]:
        """Atomically replace semantic documents and all of their vector chunks."""
        document_count = 0
        chunk_count = 0
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "delete from ai.documents where tenant_id=%s and source_type in ('schema','metric','connection')",
                (tenant_id,),
            )
            for doc in documents:
                cur.execute(
                    """
                    insert into ai.documents(tenant_id,source_type,source_ref,title,content,content_hash,metadata)
                    values (%s,%s,%s,%s,%s,%s,%s::jsonb)
                    returning id
                    """,
                    (
                        tenant_id,
                        doc["source_type"],
                        doc.get("source_ref"),
                        doc["title"],
                        doc["content"],
                        doc.get("content_hash"),
                        json.dumps(doc.get("metadata") or {}),
                    ),
                )
                document_id = cur.fetchone()["id"]
                document_count += 1
                cur.execute(
                    """
                    insert into ai.embedding_jobs(tenant_id,document_id,status,model_name,output_dimensionality,started_at,finished_at)
                    values (%s,%s,'completed',%s,%s,now(),now())
                    """,
                    (tenant_id, document_id, embedding_model, output_dimensions),
                )
                for chunk in doc["chunks"]:
                    cur.execute(
                        """
                        insert into ai.document_chunks(
                          tenant_id,document_id,chunk_index,content,token_count,content_hash,
                          embedding,embedding_model,metadata
                        ) values (%s,%s,%s,%s,%s,%s,%s::extensions.vector,%s,%s::jsonb)
                        """,
                        (
                            tenant_id,
                            document_id,
                            chunk["chunk_index"],
                            chunk["content"],
                            chunk.get("token_count"),
                            chunk.get("content_hash"),
                            chunk["embedding"],
                            embedding_model,
                            json.dumps(chunk.get("metadata") or {}),
                        ),
                    )
                    chunk_count += 1
        return {"documents": document_count, "chunks": chunk_count}

    def match_chunks(self, tenant_id: str | UUID, embedding: list[float], count: int = 8, min_similarity: float | None = 0.35) -> list[dict[str, Any]]:
        """Match only shared semantic catalog chunks, never user-uploaded file chunks."""
        vector_literal = "[" + ",".join(f"{float(v):.10g}" for v in embedding) + "]"
        return self.fetch_all(
            """
            select c.id as chunk_id,c.document_id,d.title,c.content,
                   (1-extensions.cosine_distance(c.embedding,%s::extensions.vector))::real as similarity,
                   c.metadata
            from ai.document_chunks c
            join ai.documents d on d.id=c.document_id
            where c.embedding is not null
              and c.tenant_id=%s
              and d.tenant_id=%s
              and d.source_type in ('schema','metric','connection')
              and (%s::double precision is null or (1-extensions.cosine_distance(c.embedding,%s::extensions.vector)) >= %s)
            order by extensions.cosine_distance(c.embedding,%s::extensions.vector)
            limit %s
            """,
            (
                vector_literal,
                tenant_id,
                tenant_id,
                min_similarity,
                vector_literal,
                min_similarity,
                vector_literal,
                max(1, min(count, 50)),
            ),
        )

    def match_file_chunks(
        self,
        tenant_id: str | UUID,
        user_id: str | UUID,
        file_ids: list[str | UUID],
        embedding: list[float],
        count: int = 8,
        min_similarity: float = 0.20,
    ) -> list[dict[str, Any]]:
        if not file_ids:
            return []
        vector_literal = "[" + ",".join(f"{float(v):.10g}" for v in embedding) + "]"
        return self.fetch_all(
            """
            select c.id as chunk_id,c.document_id,d.title,c.content,
                   (1-extensions.cosine_distance(c.embedding,%s::extensions.vector))::real as similarity,
                   c.metadata
            from ai.document_chunks c
            join ai.documents d on d.id=c.document_id
            where c.embedding is not null
              and d.tenant_id=%s
              and d.source_type='file'
              and d.metadata->>'user_id'=%s
              and d.id=any(%s::uuid[])
              and (1-extensions.cosine_distance(c.embedding,%s::extensions.vector)) >= %s
            order by extensions.cosine_distance(c.embedding,%s::extensions.vector)
            limit %s
            """,
            (vector_literal, tenant_id, str(user_id), [str(x) for x in file_ids], vector_literal, min_similarity, vector_literal, max(1, min(count, 30))),
        )

    def semantic_catalog_snapshot(self, tenant_id: str | UUID) -> dict[str, Any]:
        columns = self.fetch_all(
            """
            select c.table_schema, c.table_name, c.column_name, c.data_type
            from information_schema.columns c
            where c.table_schema in ('silver','gold')
            order by c.table_schema,c.table_name,c.ordinal_position
            """
        )
        metrics = self.fetch_all(
            """
            select code,name,description,preferred_source_schema,preferred_source_table,
                   sql_expression,aggregation,data_type,default_time_column,
                   allowed_dimensions,synonyms
            from ai.metric_definitions
            where active=true and (tenant_id is null or tenant_id=%s)
            order by code
            """,
            (tenant_id,),
        )
        connections = self.fetch_all(
            """
            select c.id,c.name,c.base_url,p.code as platform_code,p.name as platform_name
            from control.connections c
            join control.platforms p on p.id=c.platform_id
            where c.tenant_id=%s
            order by c.name
            """,
            (tenant_id,),
        )
        permissions = self.fetch_all(
            """
            select schema_name,table_name,tenant_column,allowed_columns,blocked_columns,max_rows
            from ai.query_permissions
            where allow_select=true and (tenant_id is null or tenant_id=%s)
            order by schema_name,table_name
            """,
            (tenant_id,),
        )
        return {"columns": columns, "metrics": metrics, "connections": connections, "permissions": permissions}

    # ------------------------------------------------------------------
    # API / observability helpers
    # ------------------------------------------------------------------
    def update_connection_resource(
        self,
        *,
        connection_id: str | UUID,
        resource_key: str,
        enabled: bool | None = None,
        sync_mode: str | None = None,
    ) -> bool:
        parts: list[str] = []
        params: list[Any] = []
        if enabled is not None:
            parts.append("enabled=%s")
            params.append(enabled)
        if sync_mode is not None:
            parts.append("sync_mode=%s::app.sync_mode")
            params.append(sync_mode)
        if not parts:
            return True
        parts.append("updated_at=now()")
        params.extend([connection_id, resource_key])
        count = self.execute(
            f"update control.connection_resources set {','.join(parts)} where connection_id=%s and resource_key=%s",
            params,
        )
        return count > 0

    def list_jobs(self, tenant_id: str | UUID, limit: int = 50) -> list[dict[str, Any]]:
        return self.fetch_all(
            """
            select id,tenant_id,trigger_type::text as trigger_type,sync_mode::text as sync_mode,
                   status::text as status,priority,total_connections,completed_connections,
                   failed_connections,total_resources,completed_resources,failed_resources,
                   queued_at,started_at,finished_at,created_at,updated_at,error_summary
            from ingestion.sync_jobs
            where tenant_id=%s
            order by created_at desc
            limit %s
            """,
            (tenant_id, limit),
        )

    def get_job(self, job_id: str | UUID) -> dict[str, Any] | None:
        return self.fetch_one(
            """
            select id,tenant_id,trigger_type::text as trigger_type,sync_mode::text as sync_mode,
                   status::text as status,priority,total_connections,completed_connections,
                   failed_connections,total_resources,completed_resources,failed_resources,
                   context,error_summary,queued_at,started_at,finished_at,created_at,updated_at
            from ingestion.sync_jobs where id=%s
            """,
            (job_id,),
        )

    def list_job_connections(self, job_id: str | UUID) -> list[dict[str, Any]]:
        return self.fetch_all(
            """
            select sjc.id,sjc.job_id,sjc.connection_id,sjc.status::text as status,
                   sjc.selected_resources,sjc.started_at,sjc.finished_at,sjc.error_summary,
                   c.name,p.code as platform_code,p.name as platform_name
            from ingestion.sync_job_connections sjc
            join control.connections c on c.id=sjc.connection_id
            join control.platforms p on p.id=c.platform_id
            where sjc.job_id=%s order by c.name
            """,
            (job_id,),
        )

    def update_job_connection_status(
        self,
        job_id: str | UUID,
        connection_id: str | UUID,
        status: str,
        error_summary: dict[str, Any] | None = None,
    ) -> None:
        self.execute(
            """
            update ingestion.sync_job_connections
            set status=%s::app.run_status,
                started_at=case when %s='running' then coalesce(started_at,now()) else started_at end,
                finished_at=case when %s in ('completed','failed','skipped','cancelled') then now() else finished_at end,
                error_summary=%s::jsonb, updated_at=now()
            where job_id=%s and connection_id=%s
            """,
            (status, status, status, json.dumps(error_summary or {}), job_id, connection_id),
        )

    def list_runs(self, job_id: str | UUID) -> list[dict[str, Any]]:
        return self.fetch_all(
            """
            select id,job_id,connection_id,resource_key,canonical_resource,sync_mode::text as sync_mode,
                   status::text as status,attempt,records_fetched,records_written,records_rejected,
                   pages_fetched,bytes_fetched,checkpoint_before,checkpoint_after,error_count,
                   error_summary,started_at,finished_at,created_at,updated_at
            from ingestion.sync_runs where job_id=%s order by created_at
            """,
            (job_id,),
        )

    def create_stage_run(
        self,
        *,
        tenant_id: str | UUID,
        job_id: str | UUID,
        stage: str,
        connection_id: str | UUID | None = None,
        resource_key: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        row = self.fetch_one(
            """
            insert into ingestion.pipeline_stage_runs(
              tenant_id,job_id,connection_id,resource_key,stage,status,metadata,started_at
            ) values (%s,%s,%s,%s,%s::app.pipeline_stage,'running',%s::jsonb,now())
            returning *
            """,
            (tenant_id, job_id, connection_id, resource_key, stage, json.dumps(metadata or {})),
        )
        assert row is not None
        return row

    def finish_stage_run(
        self,
        stage_run_id: str | UUID,
        *,
        status: str,
        input_rows: int = 0,
        output_rows: int = 0,
        rejected_rows: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.execute(
            """
            update ingestion.pipeline_stage_runs
            set status=%s::app.run_status,input_rows=%s,output_rows=%s,rejected_rows=%s,
                metadata=metadata || %s::jsonb,finished_at=now(),updated_at=now()
            where id=%s
            """,
            (status, input_rows, output_rows, rejected_rows, json.dumps(metadata or {}), stage_run_id),
        )

    def list_stage_runs(self, job_id: str | UUID) -> list[dict[str, Any]]:
        return self.fetch_all(
            """
            select id,job_id,connection_id,resource_key,stage::text as stage,status::text as status,
                   input_rows,output_rows,rejected_rows,metadata,started_at,finished_at,created_at
            from ingestion.pipeline_stage_runs where job_id=%s order by created_at
            """,
            (job_id,),
        )

    def add_job_event(
        self,
        *,
        tenant_id: str | UUID,
        event_type: str,
        message: str | None = None,
        job_id: str | UUID | None = None,
        run_id: str | UUID | None = None,
        severity: str = "info",
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.execute(
            """
            insert into ops.job_events(tenant_id,job_id,run_id,severity,event_type,message,payload)
            values (%s,%s,%s,%s::app.event_severity,%s,%s,%s::jsonb)
            """,
            (tenant_id, job_id, run_id, severity, event_type, message, json.dumps(payload or {})),
        )

    def list_job_events(self, job_id: str | UUID, limit: int = 500) -> list[dict[str, Any]]:
        return self.fetch_all(
            """
            select id,tenant_id,job_id,run_id,severity::text as severity,event_type,message,payload,created_at
            from ops.job_events where job_id=%s order by created_at asc limit %s
            """,
            (job_id, limit),
        )

    def add_error(
        self,
        *,
        message: str,
        category: str = "internal",
        code: str | None = None,
        tenant_id: str | UUID | None = None,
        job_id: str | UUID | None = None,
        run_id: str | UUID | None = None,
        connection_id: str | UUID | None = None,
        retryable: bool = False,
        detail: dict[str, Any] | None = None,
    ) -> None:
        self.execute(
            """
            insert into ops.errors(tenant_id,job_id,run_id,connection_id,category,code,message,detail,retryable)
            values (%s,%s,%s,%s,%s::app.error_category,%s,%s,%s::jsonb,%s)
            """,
            (tenant_id, job_id, run_id, connection_id, category, code, message, json.dumps(detail or {}), retryable),
        )

    def record_quality_run(
        self,
        *,
        tenant_id: str | UUID,
        sync_run_id: str | UUID | None,
        entity_name: str,
        input_records: int,
        valid_records: int,
        rejected_records: int,
    ) -> dict[str, Any]:
        quality_status = "passed" if rejected_records == 0 else ("warned" if valid_records > 0 else "failed")
        row = self.fetch_one(
            """
            insert into ops.data_quality_runs(
              tenant_id,sync_run_id,entity_name,status,input_records,valid_records,rejected_records,warning_records,finished_at
            ) values (%s,%s,%s,%s::app.quality_status,%s,%s,%s,%s,now()) returning *
            """,
            (
                tenant_id, sync_run_id, entity_name, quality_status,
                input_records, valid_records, rejected_records, rejected_records if valid_records > 0 else 0,
            ),
        )
        assert row is not None
        if rejected_records:
            self.execute(
                """
                insert into ops.data_quality_results(
                  tenant_id,quality_run_id,rule_code,status,affected_records,message,detail
                ) values (%s,%s,'silver_transform_rejected',%s::app.quality_status,%s,%s,%s::jsonb)
                """,
                (
                    tenant_id, row["id"], "warned" if valid_records > 0 else "failed", rejected_records,
                    "One or more Bronze records could not be standardized into Silver.", json.dumps({}),
                ),
            )
        return row

    _DATA_TABLES: dict[str, set[str]] = {
        "bronze": {"raw_objects", "records", "schema_snapshots"},
        "silver": {
            "customers", "customer_addresses", "products", "product_variants", "categories",
            "product_categories", "locations", "inventory_levels", "orders", "order_items",
            "order_addresses", "payments", "refunds", "refund_items", "fulfillments",
            "fulfillment_items", "returns", "return_items",
        },
        "gold": {
            "daily_sales", "product_daily", "customer_metrics", "inventory_snapshot_daily",
            "refund_daily", "fulfillment_daily", "channel_daily",
        },
    }

    def read_data_table(
        self,
        *,
        layer: str,
        table: str,
        tenant_id: str | UUID,
        connection_id: str | UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        if layer not in self._DATA_TABLES or table not in self._DATA_TABLES[layer]:
            raise ValueError("Table is not exposed by the Data Explorer API")
        full = f"{layer}.{table}"
        where = ["tenant_id=%s"]
        params: list[Any] = [tenant_id]
        columns = {r["column_name"] for r in self.fetch_all(
            "select column_name from information_schema.columns where table_schema=%s and table_name=%s",
            (layer, table),
        )}
        if connection_id is not None and "connection_id" in columns:
            where.append("connection_id=%s")
            params.append(connection_id)
        order_col = "created_at" if "created_at" in columns else ("metric_date" if "metric_date" in columns else None)
        sql = f"select * from {full} where {' and '.join(where)}"
        if order_col:
            sql += f" order by {order_col} desc nulls last"
        sql += " limit %s offset %s"
        params.extend([limit, offset])
        return self.fetch_all(sql, params)

    def tenant_overview(self, tenant_id: str | UUID) -> dict[str, Any]:
        return self.fetch_one(
            """
            select
              (select count(*) from control.connections where tenant_id=%s) as connections,
              (select count(*) from ingestion.sync_jobs where tenant_id=%s) as jobs,
              (select count(*) from bronze.records where tenant_id=%s) as bronze_records,
              (select count(*) from silver.orders where tenant_id=%s) as silver_orders,
              (select count(*) from silver.products where tenant_id=%s) as silver_products,
              (select count(*) from gold.daily_sales where tenant_id=%s) as gold_daily_rows,
              (select count(*) from ai.document_chunks where tenant_id=%s) as rag_chunks,
              (select count(*) from ai.dashboard_specs where tenant_id=%s) as dashboards
            """,
            (tenant_id,) * 8,
        ) or {}

    def rag_status(self, tenant_id: str | UUID) -> dict[str, Any]:
        return self.fetch_one(
            """
            select
              (select count(*) from ai.documents where tenant_id=%s) as documents,
              (select count(*) from ai.document_chunks where tenant_id=%s) as chunks,
              (select max(created_at) from ai.document_chunks where tenant_id=%s) as last_indexed_at
            """,
            (tenant_id, tenant_id, tenant_id),
        ) or {}

    def list_query_runs(self, tenant_id: str | UUID, limit: int = 50, user_id: str | UUID | None = None) -> list[dict[str, Any]]:
        if user_id is not None:
            return self.fetch_all(
                """
                select id,user_id,conversation_id,user_prompt,route::text as route,intent,selected_context,status::text as status,
                       model_name,prompt_tokens,completion_tokens,started_at,finished_at,error_message,created_at
                from ai.query_runs where tenant_id=%s and user_id=%s order by created_at desc limit %s
                """,
                (tenant_id, user_id, limit),
            )
        return self.fetch_all(
            """
            select id,user_id,conversation_id,user_prompt,route::text as route,intent,selected_context,status::text as status,
                   model_name,prompt_tokens,completion_tokens,started_at,finished_at,error_message,created_at
            from ai.query_runs where tenant_id=%s order by created_at desc limit %s
            """,
            (tenant_id, limit),
        )

    def get_dashboard(self, dashboard_id: str | UUID) -> dict[str, Any] | None:
        return self.fetch_one(
            """
            select id,tenant_id,user_id,query_run_id,title,description,spec,status::text as status,
                   version,created_at,updated_at from ai.dashboard_specs where id=%s
            """,
            (dashboard_id,),
        )

    def list_errors(self, tenant_id: str | UUID, limit: int = 100) -> list[dict[str, Any]]:
        return self.fetch_all(
            """
            select id,job_id,run_id,connection_id,category::text as category,code,message,
                   detail,retryable,occurred_at
            from ops.errors where tenant_id=%s order by occurred_at desc limit %s
            """,
            (tenant_id, limit),
        )

    def list_quality_runs(self, tenant_id: str | UUID, limit: int = 100) -> list[dict[str, Any]]:
        return self.fetch_all(
            """
            select id,sync_run_id,entity_name,status::text as status,input_records,valid_records,
                   rejected_records,warning_records,started_at,finished_at,metadata
            from ops.data_quality_runs where tenant_id=%s order by started_at desc limit %s
            """,
            (tenant_id, limit),
        )

    def list_tenant_events(self, tenant_id: str | UUID, limit: int = 200) -> list[dict[str, Any]]:
        return self.fetch_all(
            """
            select id,job_id,run_id,severity::text as severity,event_type,message,payload,created_at
            from ops.job_events where tenant_id=%s order by created_at desc limit %s
            """,
            (tenant_id, limit),
        )

    def sales_summary(self, tenant_id: str | UUID, days: int = 30) -> dict[str, Any]:
        return self.fetch_one(
            """
            select
              coalesce(sum(orders_count),0)::bigint as orders_count,
              coalesce(sum(units_sold),0) as units_sold,
              coalesce(sum(gross_sales),0) as gross_sales,
              coalesce(sum(refunds),0) as refunds,
              coalesce(sum(net_sales),0) as net_sales,
              case when coalesce(sum(orders_count),0)=0 then null
                   else sum(net_sales)/sum(orders_count) end as average_order_value,
              min(metric_date) as from_date,
              max(metric_date) as to_date
            from gold.daily_sales
            where tenant_id=%s and metric_date >= current_date - (%s * interval '1 day')
            """,
            (tenant_id, days),
        ) or {}

    def channel_performance(self, tenant_id: str | UUID, days: int = 30) -> list[dict[str, Any]]:
        return self.fetch_all(
            """
            select p.code as platform_code,p.name as platform_name,
                   sum(g.orders_count)::bigint as orders_count,
                   sum(g.units_sold) as units_sold,
                   sum(g.gross_sales) as gross_sales,
                   sum(g.refunds) as refunds,
                   sum(g.net_sales) as net_sales,
                   case when sum(g.orders_count)=0 then null else sum(g.net_sales)/sum(g.orders_count) end as average_order_value
            from gold.channel_daily g
            join control.platforms p on p.id=g.platform_id
            where g.tenant_id=%s and g.metric_date >= current_date - (%s * interval '1 day')
            group by p.code,p.name
            order by net_sales desc
            """,
            (tenant_id, days),
        )

    def create_embedding_job(self, tenant_id: str | UUID, document_id: str | UUID, model_name: str, output_dimensions: int = 768) -> dict[str, Any]:
        row = self.fetch_one(
            """
            insert into ai.embedding_jobs(tenant_id,document_id,status,model_name,output_dimensionality,started_at)
            values (%s,%s,'running',%s,%s,now()) returning *
            """,
            (tenant_id, document_id, model_name, output_dimensions),
        )
        assert row is not None
        return row

    def finish_embedding_job(self, embedding_job_id: str | UUID, status: str, error_message: str | None = None) -> None:
        self.execute(
            """
            update ai.embedding_jobs
            set status=%s::app.run_status,error_message=%s,finished_at=now()
            where id=%s
            """,
            (status, error_message, embedding_job_id),
        )

    def increment_usage(
        self,
        tenant_id: str | UUID,
        *,
        api_requests: int = 0,
        extracted_records: int = 0,
        stored_bytes: int = 0,
        ai_queries: int = 0,
        embedding_tokens: int = 0,
        llm_input_tokens: int = 0,
        llm_output_tokens: int = 0,
    ) -> None:
        self.execute(
            """
            insert into ops.usage_daily(
              tenant_id,usage_date,api_requests,extracted_records,stored_bytes,ai_queries,
              embedding_tokens,llm_input_tokens,llm_output_tokens
            ) values (%s,current_date,%s,%s,%s,%s,%s,%s,%s)
            on conflict (tenant_id,usage_date) do update set
              api_requests=ops.usage_daily.api_requests+excluded.api_requests,
              extracted_records=ops.usage_daily.extracted_records+excluded.extracted_records,
              stored_bytes=ops.usage_daily.stored_bytes+excluded.stored_bytes,
              ai_queries=ops.usage_daily.ai_queries+excluded.ai_queries,
              embedding_tokens=ops.usage_daily.embedding_tokens+excluded.embedding_tokens,
              llm_input_tokens=ops.usage_daily.llm_input_tokens+excluded.llm_input_tokens,
              llm_output_tokens=ops.usage_daily.llm_output_tokens+excluded.llm_output_tokens,
              updated_at=now()
            """,
            (
                tenant_id, api_requests, extracted_records, stored_bytes, ai_queries,
                embedding_tokens, llm_input_tokens, llm_output_tokens,
            ),
        )

    # ------------------------------------------------------------------
    # Generic, allowlisted frontend table access
    # ------------------------------------------------------------------
    def table_columns(self, schema: str, table: str) -> list[str]:
        """Return physical columns in ordinal order for an allowlisted table."""
        rows = self.fetch_all(
            """
            select column_name
            from information_schema.columns
            where table_schema=%s and table_name=%s
            order by ordinal_position
            """,
            (schema, table),
        )
        return [str(row["column_name"]) for row in rows]

    def read_frontend_table(
        self,
        *,
        schema: str,
        table: str,
        scope: str,
        tenant_column: str = "tenant_id",
        tenant_id: str | UUID | None = None,
        user_id: str | UUID | None = None,
        filters: dict[str, Any] | None = None,
        hidden_columns: Sequence[str] = (),
        large_columns: Sequence[str] = (),
        include_large_fields: bool = False,
        limit: int = 100,
        offset: int = 0,
        order_by: str | None = None,
        order_dir: str = "desc",
    ) -> list[dict[str, Any]]:
        """Safely read one frontend-exposed table.

        `schema`/`table` are validated against the static API registry before
        this method is called. Identifiers are still quoted with psycopg.sql.
        Tenant/user scope is enforced here rather than trusted to a caller SQL
        fragment. Equality filters are accepted only for real columns.
        """
        from psycopg import sql

        columns = self.table_columns(schema, table)
        if not columns:
            raise ValueError(f"Table not found: {schema}.{table}")

        hidden = set(hidden_columns)
        large = set(large_columns)
        selected = [
            c for c in columns
            if c not in hidden and (include_large_fields or c not in large)
        ]
        if not selected:
            raise ValueError(f"No frontend-visible columns for {schema}.{table}")

        conditions: list[Any] = []
        params: list[Any] = []

        if scope in {"tenant", "tenant_or_global"}:
            if tenant_id is None:
                raise ValueError("tenant_id is required for this table")
            if tenant_column not in columns:
                raise ValueError(f"Configured tenant column {tenant_column!r} does not exist")
            ident = sql.Identifier(tenant_column)
            if scope == "tenant_or_global":
                conditions.append(sql.SQL("({col} is null or {col} = %s)").format(col=ident))
            else:
                conditions.append(sql.SQL("{col} = %s").format(col=ident))
            params.append(tenant_id)

        elif scope == "user":
            if user_id is None:
                raise ValueError("user_id is required for this table")
            user_column = "user_id" if "user_id" in columns else "id" if "id" in columns else None
            if not user_column:
                raise ValueError(f"No user identity column found on {schema}.{table}")
            conditions.append(sql.SQL("{col} = %s").format(col=sql.Identifier(user_column)))
            params.append(user_id)

        for key, value in (filters or {}).items():
            if value is None:
                continue
            if key not in columns:
                raise ValueError(f"Unknown filter column {key!r} for {schema}.{table}")
            if key in hidden:
                raise ValueError(f"Filtering by hidden column {key!r} is not allowed")
            conditions.append(sql.SQL("{col} = %s").format(col=sql.Identifier(key)))
            params.append(value)

        safe_order = order_by if order_by in columns and order_by not in hidden else None
        if not safe_order:
            safe_order = next((c for c in ("created_at", "updated_at", "metric_date", "usage_date", "id") if c in columns), columns[0])
        direction = sql.SQL("ASC") if str(order_dir).lower() == "asc" else sql.SQL("DESC")

        statement = sql.SQL("select {cols} from {schema}.{table}").format(
            cols=sql.SQL(", ").join(sql.Identifier(c) for c in selected),
            schema=sql.Identifier(schema),
            table=sql.Identifier(table),
        )
        if conditions:
            statement += sql.SQL(" where ") + sql.SQL(" and ").join(conditions)
        statement += sql.SQL(" order by {col} {direction} limit %s offset %s").format(
            col=sql.Identifier(safe_order),
            direction=direction,
        )
        params.extend([max(1, min(int(limit), 1000)), max(0, int(offset))])

        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(statement, params)
            return list(cur.fetchall())

    def count_frontend_table(
        self,
        *,
        schema: str,
        table: str,
        scope: str,
        tenant_column: str = "tenant_id",
        tenant_id: str | UUID | None = None,
        user_id: str | UUID | None = None,
        filters: dict[str, Any] | None = None,
        hidden_columns: Sequence[str] = (),
    ) -> int:
        from psycopg import sql

        columns = self.table_columns(schema, table)
        if not columns:
            raise ValueError(f"Table not found: {schema}.{table}")
        hidden = set(hidden_columns)
        conditions: list[Any] = []
        params: list[Any] = []

        if scope in {"tenant", "tenant_or_global"}:
            if tenant_id is None:
                raise ValueError("tenant_id is required for this table")
            ident = sql.Identifier(tenant_column)
            if scope == "tenant_or_global":
                conditions.append(sql.SQL("({col} is null or {col} = %s)").format(col=ident))
            else:
                conditions.append(sql.SQL("{col} = %s").format(col=ident))
            params.append(tenant_id)
        elif scope == "user":
            if user_id is None:
                raise ValueError("user_id is required for this table")
            user_column = "user_id" if "user_id" in columns else "id" if "id" in columns else None
            if not user_column:
                raise ValueError(f"No user identity column found on {schema}.{table}")
            conditions.append(sql.SQL("{col} = %s").format(col=sql.Identifier(user_column)))
            params.append(user_id)

        for key, value in (filters or {}).items():
            if value is None:
                continue
            if key not in columns:
                raise ValueError(f"Unknown filter column {key!r} for {schema}.{table}")
            if key in hidden:
                raise ValueError(f"Filtering by hidden column {key!r} is not allowed")
            conditions.append(sql.SQL("{col} = %s").format(col=sql.Identifier(key)))
            params.append(value)

        statement = sql.SQL("select count(*)::bigint as total from {schema}.{table}").format(
            schema=sql.Identifier(schema), table=sql.Identifier(table)
        )
        if conditions:
            statement += sql.SQL(" where ") + sql.SQL(" and ").join(conditions)
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(statement, params)
            row = cur.fetchone()
            return int(row["total"] if row else 0)

    def get_frontend_record(
        self,
        *,
        schema: str,
        table: str,
        record_id: str,
        scope: str,
        tenant_column: str = "tenant_id",
        tenant_id: str | UUID | None = None,
        user_id: str | UUID | None = None,
        hidden_columns: Sequence[str] = (),
        large_columns: Sequence[str] = (),
        include_large_fields: bool = True,
    ) -> dict[str, Any] | None:
        rows = self.read_frontend_table(
            schema=schema,
            table=table,
            scope=scope,
            tenant_column=tenant_column,
            tenant_id=tenant_id,
            user_id=user_id,
            filters={"id": record_id},
            hidden_columns=hidden_columns,
            large_columns=large_columns,
            include_large_fields=include_large_fields,
            limit=1,
            offset=0,
            order_by="id",
            order_dir="asc",
        )
        return rows[0] if rows else None

    # ------------------------------------------------------------------
    # Product frontend / authenticated workspace helpers
    # ------------------------------------------------------------------
    def is_tenant_member(self, tenant_id: str | UUID, user_id: str | UUID) -> bool:
        row = self.fetch_one(
            """
            select exists(
              select 1 from iam.tenant_members
              where tenant_id=%s and user_id=%s and status::text='active'
            ) as allowed
            """,
            (tenant_id, user_id),
        )
        return bool(row and row.get("allowed"))

    def get_profile(self, user_id: str | UUID) -> dict[str, Any] | None:
        columns = self.table_columns("iam", "profiles")
        identity = "id" if "id" in columns else "user_id" if "user_id" in columns else None
        if not identity:
            return None
        return self.fetch_one(f"select * from iam.profiles where {identity}=%s", (user_id,))

    def upsert_profile(self, user_id: str | UUID, *, display_name: str | None = None, avatar_url: str | None = None, timezone: str | None = None) -> dict[str, Any]:
        columns = self.table_columns("iam", "profiles")
        identity = "id" if "id" in columns else "user_id" if "user_id" in columns else None
        if not identity:
            raise ValueError("iam.profiles has no user identity column")
        existing = self.get_profile(user_id)
        if existing is None:
            fields = [identity]
            values: list[Any] = [user_id]
            for key, value in (("display_name", display_name), ("avatar_url", avatar_url), ("timezone", timezone)):
                if key in columns and value is not None:
                    fields.append(key)
                    values.append(value)
            placeholders = ",".join(["%s"] * len(fields))
            row = self.fetch_one(
                f"insert into iam.profiles({','.join(fields)}) values ({placeholders}) returning *",
                values,
            )
            assert row is not None
            return row
        sets: list[str] = []
        values = []
        for key, value in (("display_name", display_name), ("avatar_url", avatar_url), ("timezone", timezone)):
            if key in columns and value is not None:
                sets.append(f"{key}=%s")
                values.append(value)
        if sets:
            if "updated_at" in columns:
                sets.append("updated_at=now()")
            values.append(user_id)
            self.execute(f"update iam.profiles set {','.join(sets)} where {identity}=%s", values)
        return self.get_profile(user_id) or {identity: user_id}

    def list_user_workspaces(self, user_id: str | UUID) -> list[dict[str, Any]]:
        return self.fetch_all(
            """
            select t.id,t.name,t.slug,t.timezone,tm.role::text as role,tm.status::text as membership_status,
                   t.metadata,t.created_at
            from iam.tenant_members tm
            join iam.tenants t on t.id=tm.tenant_id
            where tm.user_id=%s and tm.status::text='active'
            order by t.created_at
            """,
            (user_id,),
        )

    def create_workspace_for_user(self, user_id: str | UUID, name: str, slug: str, timezone: str = "UTC") -> dict[str, Any]:
        slug = re.sub(r"[^a-z0-9-]+", "-", slug.lower()).strip("-")
        if not slug:
            raise ValueError("A valid workspace slug is required")
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                insert into iam.tenants(name,slug,timezone,created_by,metadata)
                values (%s,%s,%s,%s,'{"plan_code":"free"}'::jsonb)
                returning *
                """,
                (name, slug, timezone, user_id),
            )
            tenant = cur.fetchone()
            cur.execute(
                """
                insert into iam.tenant_members(tenant_id,user_id,role,status,joined_at)
                values (%s,%s,'owner','active',now())
                on conflict (tenant_id,user_id) do update set role='owner',status='active',joined_at=coalesce(iam.tenant_members.joined_at,now()),updated_at=now()
                """,
                (tenant["id"], user_id),
            )
            return tenant

    def get_tenant(self, tenant_id: str | UUID) -> dict[str, Any] | None:
        return self.fetch_one("select * from iam.tenants where id=%s", (tenant_id,))

    def set_tenant_plan(self, tenant_id: str | UUID, plan_code: str) -> None:
        self.execute(
            "update iam.tenants set metadata=jsonb_set(coalesce(metadata,'{}'::jsonb),'{plan_code}',to_jsonb(%s::text),true),updated_at=now() where id=%s",
            (plan_code, tenant_id),
        )

    def usage_summary(self, tenant_id: str | UUID, days: int = 30) -> dict[str, Any]:
        row = self.fetch_one(
            """
            select coalesce(sum(api_requests),0)::bigint as api_requests,
                   coalesce(sum(extracted_records),0)::bigint as extracted_records,
                   coalesce(sum(stored_bytes),0)::bigint as stored_bytes,
                   coalesce(sum(ai_queries),0)::bigint as ai_queries,
                   coalesce(sum(embedding_tokens),0)::bigint as embedding_tokens,
                   coalesce(sum(llm_input_tokens),0)::bigint as llm_input_tokens,
                   coalesce(sum(llm_output_tokens),0)::bigint as llm_output_tokens
            from ops.usage_daily
            where tenant_id=%s and usage_date >= current_date - (%s * interval '1 day')
            """,
            (tenant_id, max(1, min(days, 366))),
        ) or {}
        connections = self.fetch_one("select count(*)::bigint as total from control.connections where tenant_id=%s", (tenant_id,))
        row["connections"] = int((connections or {}).get("total") or 0)
        row["days"] = days
        return row

    # ------------------------------------------------------------------
    # Tasks / conversations / library
    # ------------------------------------------------------------------
    def create_conversation(self, tenant_id: str | UUID, user_id: str | UUID, title: str | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        row = self.fetch_one(
            """
            insert into ai.conversations(tenant_id,user_id,title,metadata)
            values (%s,%s,%s,%s::jsonb) returning *
            """,
            (tenant_id, user_id, title, json.dumps(metadata or {})),
        )
        assert row is not None
        return row

    def get_conversation(self, conversation_id: str | UUID, tenant_id: str | UUID, user_id: str | UUID) -> dict[str, Any] | None:
        return self.fetch_one(
            "select * from ai.conversations where id=%s and tenant_id=%s and user_id=%s",
            (conversation_id, tenant_id, user_id),
        )

    def list_conversations(self, tenant_id: str | UUID, user_id: str | UUID, *, q: str | None = None, archived: bool | None = False, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        sql = """
            select c.*,
                   (select count(*) from ai.messages m where m.conversation_id=c.id) as message_count,
                   (select max(m.created_at) from ai.messages m where m.conversation_id=c.id) as last_message_at
            from ai.conversations c
            where c.tenant_id=%s and c.user_id=%s
        """
        params: list[Any] = [tenant_id, user_id]
        if archived is not None:
            sql += " and coalesce((c.metadata->>'archived')::boolean,false)=%s"
            params.append(archived)
        if q:
            sql += " and (coalesce(c.title,'') ilike %s or exists (select 1 from ai.messages m where m.conversation_id=c.id and m.content ilike %s))"
            term = f"%{q.strip()}%"
            params.extend([term, term])
        sql += " order by coalesce((c.metadata->>'pinned')::boolean,false) desc, coalesce((select max(m.created_at) from ai.messages m where m.conversation_id=c.id),c.updated_at,c.created_at) desc limit %s offset %s"
        params.extend([max(1, min(limit, 200)), max(0, offset)])
        return self.fetch_all(sql, params)

    def update_conversation(self, conversation_id: str | UUID, tenant_id: str | UUID, user_id: str | UUID, *, title: str | None = None, archived: bool | None = None, pinned: bool | None = None) -> dict[str, Any] | None:
        conv = self.get_conversation(conversation_id, tenant_id, user_id)
        if not conv:
            return None
        metadata = dict(conv.get("metadata") or {})
        if archived is not None:
            metadata["archived"] = bool(archived)
        if pinned is not None:
            metadata["pinned"] = bool(pinned)
        row = self.fetch_one(
            """
            update ai.conversations set title=coalesce(%s,title),metadata=%s::jsonb,updated_at=now()
            where id=%s and tenant_id=%s and user_id=%s
            returning *
            """,
            (title, json.dumps(metadata), conversation_id, tenant_id, user_id),
        )
        return row

    def delete_conversation(self, conversation_id: str | UUID, tenant_id: str | UUID, user_id: str | UUID) -> bool:
        return bool(self.execute(
            "delete from ai.conversations where id=%s and tenant_id=%s and user_id=%s",
            (conversation_id, tenant_id, user_id),
        ))

    def add_message(self, tenant_id: str | UUID, conversation_id: str | UUID, role: str, content: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        row = self.fetch_one(
            """
            insert into ai.messages(tenant_id,conversation_id,role,content,metadata)
            values (%s,%s,%s,%s,%s::jsonb) returning *
            """,
            (tenant_id, conversation_id, role, content, json.dumps(metadata or {}, default=str)),
        )
        assert row is not None
        self.execute("update ai.conversations set updated_at=now() where id=%s", (conversation_id,))
        return row

    def list_messages(self, conversation_id: str | UUID, tenant_id: str | UUID, *, limit: int = 200, before: datetime | None = None) -> list[dict[str, Any]]:
        sql = "select * from ai.messages where conversation_id=%s and tenant_id=%s"
        params: list[Any] = [conversation_id, tenant_id]
        if before:
            sql += " and created_at < %s"
            params.append(before)
        sql += " order by created_at asc limit %s"
        params.append(max(1, min(limit, 500)))
        return self.fetch_all(sql, params)

    def maybe_title_conversation(self, conversation_id: str | UUID, question: str) -> None:
        title = " ".join(question.strip().split())[:90]
        if title:
            self.execute("update ai.conversations set title=coalesce(nullif(title,''),%s),updated_at=now() where id=%s", (title, conversation_id))

    # ------------------------------------------------------------------
    # User files stored in ai.documents + Supabase Storage
    # ------------------------------------------------------------------
    def create_file_document(
        self,
        tenant_id: str | UUID,
        user_id: str | UUID,
        *,
        title: str,
        content: str,
        content_hash: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        metadata = dict(metadata)
        metadata["user_id"] = str(user_id)
        row = self.fetch_one(
            """
            insert into ai.documents(tenant_id,source_type,source_ref,title,content,content_hash,metadata)
            values (%s,'file',%s,%s,%s,%s,%s::jsonb) returning *
            """,
            (tenant_id, metadata.get("object_path"), title, content, content_hash, json.dumps(metadata, default=str)),
        )
        assert row is not None
        return row

    def list_file_documents(self, tenant_id: str | UUID, user_id: str | UUID, *, q: str | None = None, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        sql = """
            select id,tenant_id,source_ref,title,content_hash,metadata,created_at,updated_at
            from ai.documents
            where tenant_id=%s and source_type='file' and metadata->>'user_id'=%s
        """
        params: list[Any] = [tenant_id, str(user_id)]
        if q:
            sql += " and title ilike %s"
            params.append(f"%{q.strip()}%")
        sql += " order by created_at desc limit %s offset %s"
        params.extend([max(1, min(limit, 200)), max(0, offset)])
        return self.fetch_all(sql, params)

    def get_file_document(self, document_id: str | UUID, tenant_id: str | UUID, user_id: str | UUID) -> dict[str, Any] | None:
        return self.fetch_one(
            """
            select * from ai.documents
            where id=%s and tenant_id=%s and source_type='file' and metadata->>'user_id'=%s
            """,
            (document_id, tenant_id, str(user_id)),
        )

    def delete_file_document(self, document_id: str | UUID, tenant_id: str | UUID, user_id: str | UUID) -> bool:
        return bool(self.execute(
            "delete from ai.documents where id=%s and tenant_id=%s and source_type='file' and metadata->>'user_id'=%s",
            (document_id, tenant_id, str(user_id)),
        ))

    def get_file_context(self, tenant_id: str | UUID, user_id: str | UUID, file_ids: list[str | UUID], max_chars: int = 24000) -> list[dict[str, Any]]:
        if not file_ids:
            return []
        rows = self.fetch_all(
            """
            select id,title,content,metadata
            from ai.documents
            where tenant_id=%s and source_type='file' and metadata->>'user_id'=%s and id=any(%s::uuid[])
            order by created_at
            """,
            (tenant_id, str(user_id), [str(x) for x in file_ids]),
        )
        remaining = max_chars
        out = []
        for row in rows:
            content = str(row.get("content") or "")
            if remaining <= 0:
                break
            clipped = content[:remaining]
            remaining -= len(clipped)
            out.append({"id": row["id"], "title": row["title"], "content": clipped, "metadata": row.get("metadata") or {}})
        return out

    def library_items(self, tenant_id: str | UUID, user_id: str | UUID, *, q: str | None = None, item_type: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        if item_type in (None, "task"):
            for row in self.list_conversations(tenant_id, user_id, q=q, archived=None, limit=limit):
                items.append({"type": "task", "id": row["id"], "title": row.get("title") or "Untitled task", "created_at": row.get("created_at"), "updated_at": row.get("updated_at"), "metadata": row.get("metadata") or {}})
        if item_type in (None, "file"):
            for row in self.list_file_documents(tenant_id, user_id, q=q, limit=limit):
                items.append({"type": "file", "id": row["id"], "title": row.get("title"), "created_at": row.get("created_at"), "updated_at": row.get("updated_at"), "metadata": row.get("metadata") or {}})
        if item_type in (None, "dashboard"):
            for row in self.list_dashboards(tenant_id, limit=limit):
                if q and q.lower() not in str(row.get("title") or "").lower():
                    continue
                items.append({"type": "dashboard", "id": row["id"], "title": row.get("title"), "created_at": row.get("created_at"), "updated_at": row.get("created_at"), "metadata": {"status": row.get("status")}})
        items.sort(key=lambda x: str(x.get("updated_at") or x.get("created_at") or ""), reverse=True)
        return items[:limit]

    # ------------------------------------------------------------------
    # Uploaded Datasets
    # ------------------------------------------------------------------
    def create_uploaded_dataset(
        self,
        *,
        tenant_id: str | UUID,
        created_by: str | UUID | None,
        filename: str,
        file_type: str,
        storage_path: str,
        byte_size: int,
        checksum_sha256: str,
    ) -> dict[str, Any]:
        row = self.fetch_one(
            """
            insert into ingestion.uploaded_datasets(
                tenant_id, created_by, filename, file_type, storage_path,
                byte_size, checksum_sha256, status
            )
            values (%s, %s, %s, %s, %s, %s, %s, 'uploaded')
            returning *
            """,
            (tenant_id, created_by, filename, file_type, storage_path, byte_size, checksum_sha256),
        )
        assert row is not None
        return row

    def get_uploaded_dataset(self, dataset_id: str | UUID, tenant_id: str | UUID) -> dict[str, Any] | None:
        return self.fetch_one(
            "select * from ingestion.uploaded_datasets where id = %s and tenant_id = %s",
            (dataset_id, tenant_id),
        )

    def list_uploaded_datasets(
        self,
        tenant_id: str | UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        return self.fetch_all(
            """
            select * from ingestion.uploaded_datasets
            where tenant_id = %s
            order by created_at desc
            limit %s offset %s
            """,
            (tenant_id, max(1, min(limit, 200)), max(0, offset)),
        )

    def update_dataset_profile(
        self,
        dataset_id: str | UUID,
        tenant_id: str | UUID,
        *,
        status: str,
        has_validation_errors: bool,
        detected_entity: str | None = None,
        profile_summary: dict[str, Any] | None = None,
        quality_summary: dict[str, Any] | None = None,
        row_count: int = 0,
        error_message: str | None = None,
    ) -> dict[str, Any] | None:
        return self.fetch_one(
            """
            update ingestion.uploaded_datasets
            set status = %s,
                has_validation_errors = %s,
                detected_entity = coalesce(%s, detected_entity),
                profile_summary = coalesce(%s::jsonb, profile_summary),
                quality_summary = coalesce(%s::jsonb, quality_summary),
                row_count = %s,
                error_message = %s,
                updated_at = now()
            where id = %s and tenant_id = %s
            returning *
            """,
            (
                status,
                has_validation_errors,
                detected_entity,
                json.dumps(profile_summary or {}) if profile_summary is not None else None,
                json.dumps(quality_summary or {}) if quality_summary is not None else None,
                row_count,
                error_message,
                dataset_id,
                tenant_id,
            ),
        )

    def update_dataset_status(
        self,
        dataset_id: str | UUID,
        tenant_id: str | UUID,
        *,
        status: str,
        connection_id: str | UUID | None = None,
        mapping_config: dict[str, Any] | None = None,
        quality_summary: dict[str, Any] | None = None,
        row_count: int | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any] | None:
        sets = ["status = %s", "updated_at = now()"]
        params: list[Any] = [status]
        if connection_id is not None:
            sets.append("connection_id = %s")
            params.append(connection_id)
        if mapping_config is not None:
            sets.append("mapping_config = %s::jsonb")
            params.append(json.dumps(mapping_config))
        if quality_summary is not None:
            sets.append("quality_summary = %s::jsonb")
            params.append(json.dumps(quality_summary))
        if row_count is not None:
            sets.append("row_count = %s")
            params.append(row_count)
        if error_message is not None:
            sets.append("error_message = %s")
            params.append(error_message)

        params.extend([dataset_id, tenant_id])
        return self.fetch_one(
            f"update ingestion.uploaded_datasets set {', '.join(sets)} where id = %s and tenant_id = %s returning *",
            params,
        )

    def purge_connection_silver_records(self, connection_id: str | UUID) -> None:
        with self.connection() as conn, conn.cursor() as cur:
            for table in (
                "silver.order_items",
                "silver.orders",
                "silver.product_variants",
                "silver.products",
                "silver.customers",
                "silver.inventory_levels",
                "silver.refund_items",
                "silver.refunds",
                "silver.fulfillment_items",
                "silver.fulfillments",
            ):
                cur.execute(f"delete from {table} where connection_id = %s", (connection_id,))

    def prune_stale_silver_records(
        self,
        table: str,
        connection_id: str | UUID,
        active_source_ids: Sequence[str],
    ) -> int:
        if not re.fullmatch(r"silver\.[a-z_][a-z0-9_]*", table):
            raise ValueError(f"Unsafe table name: {table}")
        if not active_source_ids:
            return 0
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                f"delete from {table} where connection_id = %s and not (source_id = any(%s::text[]))",
                (connection_id, list(active_source_ids)),
            )
            return cur.rowcount