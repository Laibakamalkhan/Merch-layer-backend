from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Any, Sequence
from uuid import UUID

from commerce_connector.core.models import ConnectorPage, RequestSpec, ResponseSpec
from commerce_connector.platform.bronze import BronzeWriter
from commerce_connector.platform.datasets.parsers import parse_dataset_stream
from commerce_connector.platform.db import PostgresGateway
from commerce_connector.platform.gold import GoldRefresher
from commerce_connector.platform.silver import SilverTransformer

logger = logging.getLogger("commerce_connector.datasets")

# In-memory tenant concurrency lock for Gold refreshes
_TENANT_LOCKS: dict[str, asyncio.Lock] = {}


def _get_tenant_lock(tenant_id: str) -> asyncio.Lock:
    if tenant_id not in _TENANT_LOCKS:
        _TENANT_LOCKS[tenant_id] = asyncio.Lock()
    return _TENANT_LOCKS[tenant_id]


class DatasetIngestionOrchestrator:
    def __init__(
        self,
        *,
        db: PostgresGateway,
        bronze: BronzeWriter,
        silver: SilverTransformer,
        gold: GoldRefresher,
    ):
        self.db = db
        self.bronze = bronze
        self.silver = silver
        self.gold = gold

    async def ingest_dataset(
        self,
        *,
        tenant_id: str,
        user_id: str | None,
        dataset_id: str,
        target_entity: str,
        column_mappings: dict[str, str],
        natural_key_column: str | None = None,
        raw_file_bytes: bytes,
        rebuild_rag_after_sync: bool = False,
        indexer: Any | None = None,
    ) -> dict[str, Any]:
        dataset = await asyncio.to_thread(self.db.get_uploaded_dataset, dataset_id, tenant_id)
        if not dataset:
            raise KeyError(f"Dataset not found: {dataset_id}")

        # Check / Create Connection
        connection_id = dataset.get("connection_id")
        if not connection_id:
            clean_name = f"File: {dataset['filename']} ({str(dataset_id)[:8]})"
            connection = await asyncio.to_thread(
                self.db.create_connection,
                tenant_id=tenant_id,
                platform_code="file_upload",
                name=clean_name,
                base_url=None,
                config={"dataset_id": dataset_id, "filename": dataset["filename"]},
                metadata={"source_type": "file_upload", "file_type": dataset["file_type"]},
                enabled_resources=[target_entity],
            )
            connection_id = str(connection["id"])

        await asyncio.to_thread(
            self.db.update_dataset_status,
            dataset_id,
            tenant_id,
            status="ingesting",
            connection_id=connection_id,
            mapping_config=column_mappings,
        )

        try:
            # Parse rows from raw bytes
            raw_rows = list(parse_dataset_stream(dataset["file_type"], raw_file_bytes))
            if not raw_rows:
                raise ValueError("Dataset has no data rows to ingest")

            normalized_records: list[dict[str, Any]] = []
            active_source_ids: list[str] = []
            seen_source_ids: set[str] = set()

            for idx, raw_row in enumerate(raw_rows):
                norm: dict[str, Any] = {}
                for src_col, target_field in column_mappings.items():
                    if src_col in raw_row:
                        norm[target_field] = raw_row[src_col]

                # Determine Record Identity
                source_id = None
                if natural_key_column and raw_row.get(natural_key_column):
                    source_id = str(raw_row[natural_key_column]).strip()
                    if source_id in seen_source_ids:
                        raise ValueError(
                            f"Duplicate natural identifier '{source_id}' encountered at row {idx + 1}. "
                            "Single-entity uploads cannot have duplicate natural keys."
                        )
                    seen_source_ids.add(source_id)
                elif "source_id" in norm and norm["source_id"]:
                    source_id = str(norm["source_id"]).strip()
                    if source_id in seen_source_ids:
                        raise ValueError(
                            f"Duplicate natural identifier '{source_id}' encountered at row {idx + 1}."
                        )
                    seen_source_ids.add(source_id)
                else:
                    # Anonymous Dataset: Assign deterministic intra-file ordinal
                    source_id = f"anon_{idx + 1:06d}"

                norm["source_id"] = source_id
                active_source_ids.append(source_id)
                normalized_records.append(norm)

            job = None
            run = None
            try:
                job = await asyncio.to_thread(self.db.create_job, tenant_id, [connection_id], "manual")
                await asyncio.to_thread(self.db.start_job, job["id"])
                run = await asyncio.to_thread(
                    self.db.create_run,
                    tenant_id=tenant_id,
                    job_id=job["id"],
                    connection_id=connection_id,
                    resource_key=target_entity,
                    canonical_resource=target_entity,
                    sync_mode="incremental" if natural_key_column or "source_id" in column_mappings.values() else "full",
                )
                job_id = str(job["id"])
                run_id = str(run["id"])
            except Exception as exc:
                logger.warning("Could not initialize sync job/run records: %s", exc)
                job_id = str(dataset_id)
                run_id = str(dataset_id)

            # Stage 1: Bronze Persistence
            mock_request = RequestSpec(
                method="GET",
                url=f"file://{dataset['storage_path']}",
            )
            mock_response = ResponseSpec(
                status_code=200,
                url=f"file://{dataset['storage_path']}",
                headers={"content-type": dataset["file_type"]},
                data=normalized_records,
                raw_bytes=raw_file_bytes,
            )
            mock_page = ConnectorPage(
                resource=target_entity,
                page_number=1,
                request=mock_request,
                response=mock_response,
                records=normalized_records,
                record_count=len(normalized_records),
            )

            bronze_result = await self.bronze.write_page(
                tenant_id=tenant_id,
                job_id=job_id,
                run_id=run_id,
                connection_id=connection_id,
                resource_key=target_entity,
                page=mock_page,
            )

            # Stage 2: Silver Transformation
            # If anonymous dataset, purge previous records for this connection first
            if not natural_key_column and "source_id" not in column_mappings.values():
                await asyncio.to_thread(self.db.purge_connection_silver_records, connection_id)

            transform_result = await self.silver.transform_records(
                tenant_id=tenant_id,
                connection_id=connection_id,
                platform="file_upload",
                resource=target_entity,
                records=bronze_result["records"],
            )

            # If natural key dataset, prune records that were deleted in the new file
            if natural_key_column or "source_id" in column_mappings.values():
                await asyncio.to_thread(
                    self.db.prune_stale_silver_records,
                    f"silver.{target_entity}",
                    connection_id,
                    active_source_ids,
                )

            # Stage 3: Atomic Gold Refresh with Tenant Concurrency Lock
            tenant_lock = _get_tenant_lock(tenant_id)
            async with tenant_lock:
                await asyncio.to_thread(self.gold.refresh_tenant, tenant_id)

            # Finalize sync run and job records if created
            if run and job:
                try:
                    await asyncio.to_thread(
                        self.db.finish_run,
                        str(run["id"]),
                        status="completed",
                        records_fetched=len(normalized_records),
                        records_written=transform_result["written"],
                        records_rejected=transform_result["rejected"],
                        pages_fetched=1,
                        bytes_fetched=len(raw_file_bytes),
                    )
                    await asyncio.to_thread(self.db.update_job_connection_status, str(job["id"]), connection_id, "completed")
                    await asyncio.to_thread(self.db.finalize_job, job["id"])
                    await asyncio.to_thread(
                        self.db.record_quality_run,
                        tenant_id=tenant_id,
                        sync_run_id=str(run["id"]),
                        entity_name=target_entity,
                        input_records=len(normalized_records),
                        valid_records=transform_result["written"],
                        rejected_records=transform_result["rejected"],
                    )
                except Exception as sync_exc:
                    logger.warning("Could not finalize sync job tracking: %s", sync_exc)

            # Stage 4: Optional RAG Indexing
            rag_result = None
            if rebuild_rag_after_sync and indexer:
                try:
                    rag_result = await asyncio.to_thread(indexer.rebuild, tenant_id)
                except Exception as exc:
                    logger.warning("RAG rebuild failed after dataset ingestion: %s", exc)

            profile_summary = dataset.get("profile_summary") or {}
            quality_summary = {
                "input_records": len(normalized_records),
                "silver_written": transform_result["written"],
                "silver_rejected": transform_result["rejected"],
                "available_metrics": profile_summary.get("available_metrics") or [],
                "unavailable_metrics": profile_summary.get("unavailable_metrics") or [],
                "detected_entity": dataset.get("detected_entity") or profile_summary.get("detected_entity"),
            }

            final_dataset = await asyncio.to_thread(
                self.db.update_dataset_status,
                dataset_id,
                tenant_id,
                status="completed",
                connection_id=connection_id,
                mapping_config=column_mappings,
                quality_summary=quality_summary,
                row_count=transform_result["written"],
                error_message=None,
            )

            return {
                "dataset": final_dataset,
                "connection_id": connection_id,
                "records_written": transform_result["written"],
                "records_rejected": transform_result["rejected"],
                "rag": rag_result,
            }

        except Exception as exc:
            logger.exception("Dataset ingestion failed for dataset %s, tenant %s", dataset_id, tenant_id)
            if 'run' in locals() and run:
                try:
                    await asyncio.to_thread(
                        self.db.finish_run,
                        str(run["id"]),
                        status="failed",
                        records_fetched=len(normalized_records) if "normalized_records" in locals() else 0,
                        error_summary={"error": str(exc)},
                    )
                except Exception:
                    pass
            if 'job' in locals() and job:
                try:
                    await asyncio.to_thread(self.db.update_job_connection_status, str(job["id"]), connection_id, "failed")
                    await asyncio.to_thread(self.db.finalize_job, job["id"])
                except Exception:
                    pass

            await asyncio.to_thread(
                self.db.update_dataset_status,
                dataset_id,
                tenant_id,
                status="failed",
                error_message=str(exc)[:500],
            )
            raise
