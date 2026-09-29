from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from typing import Any

from commerce_connector.core.connector import UniversalCommerceConnector
from commerce_connector.platform.bronze import BronzeWriter
from commerce_connector.platform.db import PostgresGateway
from commerce_connector.platform.gold import GoldRefresher
from commerce_connector.platform.manifest_runtime import RuntimeManifestFactory
from commerce_connector.platform.silver import SilverTransformer


@dataclass(slots=True)
class ResourceSyncResult:
    resource: str
    status: str
    pages: int = 0
    fetched: int = 0
    silver_written: int = 0
    rejected: int = 0
    error: str | None = None


class SyncOrchestrator:
    def __init__(
        self,
        *,
        db: PostgresGateway,
        manifest_factory: RuntimeManifestFactory,
        bronze: BronzeWriter,
        silver: SilverTransformer,
        gold: GoldRefresher,
        max_concurrency: int = 5,
        max_pages_per_resource: int | None = None,
    ):
        self.db = db
        self.manifest_factory = manifest_factory
        self.bronze = bronze
        self.silver = silver
        self.gold = gold
        self.max_concurrency = max_concurrency
        self.max_pages_per_resource = max_pages_per_resource

    async def run(self, tenant_id: str, connection_ids: list[str]) -> dict[str, Any]:
        if not connection_ids:
            raise ValueError("Select at least one connection")
        job = await asyncio.to_thread(self.db.create_job, tenant_id, connection_ids)
        await asyncio.to_thread(self.db.start_job, job["id"])
        limiter = asyncio.Semaphore(self.max_concurrency)

        async def run_connection(connection_id: str):
            async with limiter:
                return await self._run_connection(tenant_id, str(job["id"]), connection_id)

        await asyncio.to_thread(
            self.db.add_job_event,
            tenant_id=tenant_id,
            job_id=str(job["id"]),
            event_type="job_started",
            message="Multi-connection sync job started.",
            payload={"connection_ids": connection_ids},
        )
        results = await asyncio.gather(
            *(asyncio.create_task(run_connection(cid)) for cid in connection_ids),
            return_exceptions=False,
        )
        gold_stage = await asyncio.to_thread(
            self.db.create_stage_run,
            tenant_id=tenant_id,
            job_id=str(job["id"]),
            stage="gold",
            metadata={"scope": "tenant"},
        )
        try:
            await asyncio.to_thread(self.gold.refresh_tenant, tenant_id)
            await asyncio.to_thread(self.db.finish_stage_run, str(gold_stage["id"]), status="completed")
        except Exception as exc:
            await asyncio.to_thread(
                self.db.finish_stage_run,
                str(gold_stage["id"]),
                status="failed",
                metadata={"error": f"{type(exc).__name__}: {exc}"},
            )
            await asyncio.to_thread(
                self.db.add_error,
                tenant_id=tenant_id,
                job_id=str(job["id"]),
                category="internal",
                code="gold_refresh_failed",
                message=f"{type(exc).__name__}: {exc}",
            )
        status = await asyncio.to_thread(self.db.finalize_job, job["id"])
        total_records = sum(
            int(r.get("fetched", 0))
            for connection_result in results
            for r in connection_result.get("resources", [])
        )
        total_pages = sum(
            int(r.get("pages", 0))
            for connection_result in results
            for r in connection_result.get("resources", [])
        )
        await asyncio.to_thread(
            self.db.increment_usage,
            tenant_id,
            api_requests=total_pages,
            extracted_records=total_records,
        )
        await asyncio.to_thread(
            self.db.add_job_event,
            tenant_id=tenant_id,
            job_id=str(job["id"]),
            event_type="job_finished",
            message=f"Sync job finished with status {status}.",
            payload={"status": status},
        )
        return {"job_id": str(job["id"]), "status": status, "connections": results}

    async def _run_connection(self, tenant_id: str, job_id: str, connection_id: str) -> dict[str, Any]:
        connection = await asyncio.to_thread(self.db.get_connection, connection_id)
        await asyncio.to_thread(self.db.update_job_connection_status, job_id, connection_id, "running")
        manifest = await asyncio.to_thread(self.manifest_factory.build, connection_id)
        resource_rows = await asyncio.to_thread(self.db.get_connection_resources, connection_id, True)
        results: list[dict[str, Any]] = []

        async with UniversalCommerceConnector(manifest) as connector:
            for resource_row in resource_rows:
                resource = resource_row["resource_key"]
                if resource not in connector.resources():
                    results.append(asdict(ResourceSyncResult(resource, "skipped", error="Resource not present in local manifest")))
                    continue
                result = await self._run_resource(
                    tenant_id=tenant_id,
                    job_id=job_id,
                    connection=connection,
                    resource_row=resource_row,
                    connector=connector,
                )
                results.append(asdict(result))

        ok = any(r["status"] == "completed" for r in results)
        failed = any(r["status"] == "failed" for r in results)
        await asyncio.to_thread(self.db.mark_connection_test, connection_id, ok)
        await asyncio.to_thread(
            self.db.update_job_connection_status,
            job_id,
            connection_id,
            "failed" if (failed and not ok) else "completed",
            {"resource_results": results} if failed else None,
        )
        return {
            "connection_id": connection_id,
            "name": connection["name"],
            "platform": connection["platform_code"],
            "resources": results,
        }

    async def _run_resource(
        self,
        *,
        tenant_id: str,
        job_id: str,
        connection: dict[str, Any],
        resource_row: dict[str, Any],
        connector: UniversalCommerceConnector,
    ) -> ResourceSyncResult:
        resource = resource_row["resource_key"]
        run = await asyncio.to_thread(
            self.db.create_run,
            tenant_id=tenant_id,
            job_id=job_id,
            connection_id=str(connection["id"]),
            resource_key=resource,
            canonical_resource=resource_row.get("canonical_resource"),
            sync_mode=resource_row.get("sync_mode") or "incremental",
        )
        pages = fetched = written = rejected = bytes_fetched = 0
        last_checkpoint = None
        extract_stage = await asyncio.to_thread(
            self.db.create_stage_run,
            tenant_id=tenant_id, job_id=job_id, connection_id=str(connection["id"]),
            resource_key=resource, stage="extract",
        )
        bronze_stage = await asyncio.to_thread(
            self.db.create_stage_run,
            tenant_id=tenant_id, job_id=job_id, connection_id=str(connection["id"]),
            resource_key=resource, stage="bronze",
        )
        silver_stage = await asyncio.to_thread(
            self.db.create_stage_run,
            tenant_id=tenant_id, job_id=job_id, connection_id=str(connection["id"]),
            resource_key=resource, stage="silver",
        )
        try:
            resume_state = await asyncio.to_thread(self.db.get_checkpoint, str(connection["id"]), resource)
            async for page in connector.stream(
                resource,
                resume_state=resume_state,
                max_pages=self.max_pages_per_resource,
            ):
                pages += 1
                fetched += page.record_count or 0
                bytes_fetched += len(page.response.raw_bytes or b"")
                bronze_result = await self.bronze.write_page(
                    tenant_id=tenant_id,
                    job_id=job_id,
                    run_id=str(run["id"]),
                    connection_id=str(connection["id"]),
                    resource_key=resource,
                    page=page,
                )
                transform = await self.silver.transform_records(
                    tenant_id=tenant_id,
                    connection_id=str(connection["id"]),
                    platform=connection["platform_code"],
                    resource=resource,
                    records=bronze_result["records"],
                )
                written += transform["written"]
                rejected += transform["rejected"]
                if page.checkpoint:
                    last_checkpoint = page.checkpoint
                    await asyncio.to_thread(
                        self.db.upsert_checkpoint,
                        tenant_id,
                        str(connection["id"]),
                        resource,
                        page.checkpoint,
                        str(run["id"]),
                    )
            await asyncio.to_thread(
                self.db.finish_run,
                str(run["id"]),
                status="completed",
                records_fetched=fetched,
                records_written=written,
                records_rejected=rejected,
                pages_fetched=pages,
                bytes_fetched=bytes_fetched,
                checkpoint_after=last_checkpoint,
            )
            await asyncio.to_thread(self.db.finish_stage_run, str(extract_stage["id"]), status="completed", input_rows=0, output_rows=fetched)
            await asyncio.to_thread(self.db.finish_stage_run, str(bronze_stage["id"]), status="completed", input_rows=fetched, output_rows=fetched)
            await asyncio.to_thread(self.db.finish_stage_run, str(silver_stage["id"]), status="completed", input_rows=fetched, output_rows=written, rejected_rows=rejected)
            await asyncio.to_thread(
                self.db.record_quality_run,
                tenant_id=tenant_id,
                sync_run_id=str(run["id"]),
                entity_name=resource_row.get("canonical_resource") or resource,
                input_records=fetched,
                valid_records=written,
                rejected_records=rejected,
            )
            await asyncio.to_thread(self.db.set_resource_permission, str(connection["id"]), resource, "allowed", None)
            return ResourceSyncResult(resource, "completed", pages, fetched, written, rejected)
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            lowered = message.lower()
            if "401" in lowered or "authentication" in lowered:
                permission = "denied"
                code = "authentication"
            elif "403" in lowered or "access_denied" in lowered or "permission" in lowered:
                permission = "denied"
                code = "authorization"
            else:
                permission = resource_row.get("permission_status") or "unknown"
                code = "runtime_error"
            try:
                await asyncio.to_thread(self.db.set_resource_permission, str(connection["id"]), resource, permission, code)
                await asyncio.to_thread(
                    self.db.finish_run,
                    str(run["id"]),
                    status="failed",
                    records_fetched=fetched,
                    records_written=written,
                    records_rejected=rejected,
                    pages_fetched=pages,
                    bytes_fetched=bytes_fetched,
                    checkpoint_after=last_checkpoint,
                    error_summary={"error": message},
                )
                for stage in (extract_stage, bronze_stage, silver_stage):
                    await asyncio.to_thread(
                        self.db.finish_stage_run,
                        str(stage["id"]),
                        status="failed",
                        input_rows=fetched,
                        output_rows=written,
                        rejected_rows=rejected,
                        metadata={"error": message},
                    )
                category = code if code in {"authentication", "authorization"} else "internal"
                await asyncio.to_thread(
                    self.db.add_error,
                    tenant_id=tenant_id,
                    job_id=job_id,
                    run_id=str(run["id"]),
                    connection_id=str(connection["id"]),
                    category=category,
                    code=code,
                    message=message,
                    detail={"resource": resource},
                )
            except Exception as log_exc:  # error record karte waqt DB ka masla ho to bhi sync na ruke
                message = f"{message} (error log bhi save nahi hua: {type(log_exc).__name__})"
            return ResourceSyncResult(resource, "failed", pages, fetched, written, rejected, message)