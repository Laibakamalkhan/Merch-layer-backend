from __future__ import annotations

import asyncio
import logging

from pathlib import Path
from typing import Any

from commerce_connector.core.connector import UniversalCommerceConnector

from commerce_connector.platform.ai_analyst import AIAnalyst
from commerce_connector.platform.bronze import BronzeWriter
from commerce_connector.platform.db import PostgresGateway
from commerce_connector.platform.datasets.ingestor import DatasetIngestionOrchestrator
from commerce_connector.platform.gold import GoldRefresher
from commerce_connector.platform.groq import GroqClient
from commerce_connector.platform.manifest_runtime import RuntimeManifestFactory
from commerce_connector.platform.orchestrator import SyncOrchestrator
from commerce_connector.platform.rag import SemanticIndexer
from commerce_connector.platform.settings import PlatformSettings
from commerce_connector.platform.silver import SilverTransformer
from commerce_connector.platform.storage import SupabaseStorageClient
from commerce_connector.platform.user_files import UserFileStorage


def _detail_after(text: str, marker: str, limit: int = 200) -> str:
    """Store ke jawab ka chhota hissa (secret nahi hota) taake asli wajah nazar aaye."""
    if marker in text:
        return text.split(marker, 1)[1].strip()[:limit]
    return text[:limit]


def friendly_test_error(exc: Exception, platform: str) -> str:
    """Technical error ko aasaan message mein badalta hai (frontend yahi dikhata hai)."""
    text = str(exc)
    name = type(exc).__name__
    if "token exchange failed" in text:  # Shopify Client ID/Secret wala rasta
        detail = _detail_after(text, "failed:")
        if "shop_not_permitted" in text or "cannot be performed on this shop" in text:
            return ("Shopify ne is store par Client Credentials ki ijazat nahi di. Yeh tareeqa tab chalta hai jab app aur store "
                    "ek hi Shopify organization/account ke hon, aur app us store par install ho. "
                    f"Shopify ka jawab: {detail}")
        if "invalid_client" in text or "HTTP 401" in text or "HTTP 400" in text:
            return ("Shopify ne Client ID/Client Secret qubool nahi kiye. Dev Dashboard > App > Settings se dono dobara copy karein "
                    f"(secret ke shuru/aakhir mein space na ho) aur app us store par install karein. Shopify ka jawab: {detail}")
        return f"Shopify token exchange fail hua: {detail}"
    if "ACCESS_DENIED" in text or "not approved to access" in text:
        if "Customer object" in text or "personally identifiable" in text:
            return ("Shopify ke is store ke plan par customers ka data (naam, email, phone) allowed nahi hai. "
                    "Yeh sirf Shopify, Advanced ya Plus plan par milta hai.")
        return ("Shopify ne is data ki ijazat nahi di (ACCESS_DENIED). App ke scopes (read_orders, read_products, "
                "read_customers, read_inventory) check karein aur app ko dobara install karein.")
    if "HTTP 401" in text or "HTTP 403" in text:
        detail = _detail_after(text, "HTTP 401:") if "HTTP 401" in text else _detail_after(text, "HTTP 403:")
        if platform == "shopify":
            return ("Shopify ne token qubool nahi kiya. 2026 ke baad nayi app se 'shpat_' token nahi milta, balki Dev Dashboard se "
                    "Client ID + Client Secret milta hai. Agar aapne Client Secret ko 'access token' ke khane mein daala tha to woh galat "
                    f"hai. Shopify ka jawab: {detail}")
        if platform == "woocommerce":
            return ("WooCommerce ne keys qubool nahi kin (401/403). Consumer Key (ck_...) aur Consumer Secret (cs_...) check karein "
                    f"aur key ki permission 'Read' ya 'Read/Write' honi chahiye. Jawab: {detail}")
        return f"Store ne credentials qubool nahi kiye (401/403). Token/keys aur permissions check karein. Jawab: {detail}"
    if "credentials missing" in text:
        return "Credentials poore nahi hain: Client ID + Client Secret dono bharein (ya purana access token)."
    if "HTTP 404" in text:
        return "Store URL ya API path nahi mila (404). URL check karein, jaise https://your-store.myshopify.com"
    if name == "SecurityError":
        return ("Store URL qubool nahi hua: URL https:// se shuru hona chahiye aur public hona chahiye "
                f"(localhost/private network allowed nahi). Detail: {text}")
    if "ConnectError" in name or "ConnectTimeout" in name or "Timeout" in name or "getaddrinfo" in text:
        return "Store tak pohanch nahi saka. URL ki spelling aur internet connection check karein."
    return f"Connection test fail hua: {name}: {text[:300]}"


class CommercePlatformService:
    def __init__(self, settings: PlatformSettings, project_root: str | Path):
        settings.validate_database()
        self.settings = settings
        self.project_root = Path(project_root)
        self.db = PostgresGateway(settings.database_url)
        self.manifest_factory = RuntimeManifestFactory(self.db, self.project_root / "manifests")
        storage = None
        if settings.supabase_url and settings.supabase_service_role_key:
            storage = SupabaseStorageClient(
                settings.supabase_url,
                settings.supabase_service_role_key,
                settings.bronze_bucket,
            )
        self.bronze = BronzeWriter(self.db, storage, settings.bronze_bucket)
        self.user_files = None
        if settings.supabase_url and settings.supabase_service_role_key:
            self.user_files = UserFileStorage(
                settings.supabase_url,
                settings.supabase_service_role_key,
                settings.user_files_bucket,
            )
        self.silver = SilverTransformer(self.db, self.project_root / "mappings")
        self.gold = GoldRefresher(self.db)
        self.sync_engine = SyncOrchestrator(
            db=self.db,
            manifest_factory=self.manifest_factory,
            bronze=self.bronze,
            silver=self.silver,
            gold=self.gold,
            max_concurrency=settings.max_concurrent_connections,
            max_pages_per_resource=settings.max_pages_per_resource,
        )
        self.datasets_engine = DatasetIngestionOrchestrator(
            db=self.db,
            bronze=self.bronze,
            silver=self.silver,
            gold=self.gold,
        )
        self.llm = None
        self.indexer = None
        self.analyst = None
        if settings.llm_provider == "groq" and settings.groq_api_key:
            self.llm = GroqClient(
                settings.groq_api_key,
                model=settings.groq_model,
                embedding_dimensions=settings.embedding_dimensions,
                embedding_provider=settings.embedding_provider,
                ollama_base_url=settings.ollama_base_url,
                ollama_embedding_model=settings.ollama_embedding_model,
                use_system_proxy=settings.groq_use_system_proxy,
            )
            self.indexer = SemanticIndexer(self.db, self.llm)
            self.analyst = AIAnalyst(self.db, self.llm)

    def health(self) -> dict[str, Any]:
        return self.db.ping()

    def rebuild_rag(self, tenant_id: str) -> dict[str, int]:
        if not self.indexer:
            raise RuntimeError("Groq API key is required")
        result = self.indexer.rebuild(tenant_id)
        self.db.increment_usage(tenant_id, api_requests=1)
        return result

    def ask_ai(
        self,
        tenant_id: str,
        question: str,
        *,
        user_id: str | None = None,
        conversation_id: str | None = None,
        reasoning: bool = False,
        model_id: str = "merchlayer-2.0",
        file_ids: list[str] | None = None,
        include_debug: bool = False,
    ) -> dict[str, Any]:
        if not self.analyst:
            raise RuntimeError("Groq API key is required")
        if model_id != "merchlayer-2.0":
            raise ValueError(f"Unsupported model_id: {model_id}")
        result = self.analyst.ask(
            tenant_id,
            question,
            user_id=user_id,
            conversation_id=conversation_id,
            reasoning=reasoning,
            file_ids=file_ids or [],
            include_debug=include_debug,
        )
        self.db.increment_usage(tenant_id, api_requests=1, ai_queries=1)
        return result

    async def run_pipeline(
        self,
        *,
        tenant_id: str,
        connection_ids: list[str],
        rebuild_rag_after_sync: bool = False,
    ) -> dict[str, Any]:
        result = await self.sync_engine.run(tenant_id, connection_ids)
        if rebuild_rag_after_sync:
            if not self.indexer:
                # Pehle yeh chup-chaap skip ho jata tha. Ab saaf likha aata hai ke kyun index nahi bana.
                result["rag_error"] = "GROQ_API_KEY set nahi hai, isliye AI index nahi bana."
            else:
                try:
                    # to_thread: embedding ke sync HTTP calls poora server block na karein.
                    result["rag"] = await asyncio.to_thread(self.indexer.rebuild, tenant_id)
                except Exception as exc:  # sync ka data save ho chuka hai, RAG fail hone se sync fail na dikhe
                    logging.getLogger("commerce_connector.service").exception("RAG rebuild failed")
                    result["rag_error"] = f"{type(exc).__name__}: {exc}"
        return result

    @staticmethod
    def _classify_resource_error(exc: Exception) -> str:
        """authentication = token/keys galat (sab resources fail), authorization = sirf is resource ki ijazat nahi."""
        low = f"{type(exc).__name__}: {exc}".lower()
        if "access_denied" in low or "not approved" in low or "http 403" in low or "permission" in low:
            return "authorization"
        if "http 401" in low or "token exchange failed" in low or "credentials missing" in low or "authentication" in low:
            return "authentication"
        return "other"

    async def test_connection(self, connection_id: str) -> dict[str, Any]:
        """Har enabled resource ko ek page ke liye test karta hai.

        FIX #4: pehle sirf pehla resource (alphabet ke hisaab se 'customers') test hota tha. Agar store ke plan par
        ek resource allowed na ho (jaise Shopify Basic/dev store par customer PII) to poora connection fail ho jata tha.
        Ab connection tab pass hota hai jab kam az kam ek resource chal jaye; jo resources allowed nahi unhe skip
        (disable) kar ke batate hain.
        """
        connection = self.db.get_connection(connection_id)
        manifest = self.manifest_factory.build(connection_id)
        resources = self.db.get_connection_resources(connection_id, enabled_only=True)
        if not resources:
            raise ValueError("Connection has no enabled resources")

        working: list[str] = []
        skipped: list[dict[str, str]] = []
        first_error: Exception | None = None
        auth_error: Exception | None = None
        auth_failed = False
        logger = logging.getLogger("commerce_connector.service")
        try:
            async with UniversalCommerceConnector(manifest) as connector:
                available = set(connector.resources())
                for row in resources:
                    key = row["resource_key"]
                    if key not in available:
                        skipped.append({"resource": key, "reason": "Local manifest mein maujood nahi"})
                        continue
                    try:
                        async for _page in connector.stream(key, max_pages=1):
                            break
                        working.append(key)
                        self.db.set_resource_permission(connection_id, key, "allowed", None)
                    except Exception as exc:
                        kind = self._classify_resource_error(exc)
                        first_error = first_error or exc
                        logger.warning("Resource test failed platform=%s resource=%s kind=%s error=%s: %s",
                                       connection["platform_code"], key, kind, type(exc).__name__, str(exc)[:500])
                        if kind == "authentication":
                            auth_failed = True
                            auth_error = exc
                            break  # token hi galat hai, baaqi resources test karne ka faida nahi
                        skipped.append({"resource": key, "reason": friendly_test_error(exc, connection["platform_code"])})
                        if kind == "authorization":
                            self.db.set_resource_permission(connection_id, key, "denied", "authorization")
                            self.db.update_connection_resource(connection_id=connection_id, resource_key=key, enabled=False)
        except Exception as exc:  # connector khulte hi fail (jaise galat URL)
            first_error = first_error or exc
            logger.warning("Connection test failed platform=%s error=%s: %s",
                           connection["platform_code"], type(exc).__name__, str(exc)[:500])

        base = {
            "connection_id": connection_id,
            "platform": connection["platform_code"],
            "working_resources": working,
            "skipped_resources": skipped,
        }
        if working and not auth_failed:
            self.db.mark_connection_test(connection_id, True)
            message = f"Connected! Chal rahe resources: {', '.join(working)}."
            if skipped:
                names = ", ".join(x["resource"] for x in skipped)
                message += f" Skip hue (is store par allowed nahi): {names}."
            return {"ok": True, "tested_resource": working[0], **base, "message": message}

        self.db.mark_connection_test(connection_id, False)
        error = auth_error or first_error or ValueError("Koi resource test nahi ho saka")
        if auth_failed:
            # Token/keys galat hain: asal wajah wahi hai, sab resources par lagu hoti hai.
            message = friendly_test_error(error, connection["platform_code"])
        else:
            # FIX: pehle sirf pehla error (alphabet mein 'customers') dikhta tha aur asli wajah chhup jati thi.
            # Ab har resource ka apna error dikhate hain.
            details = " | ".join(f"{x['resource']}: {x['reason']}" for x in skipped) or friendly_test_error(error, connection["platform_code"])
            message = f"Koi bhi resource nahi chala. {details}"
        return {
            "ok": False,
            "tested_resource": resources[0]["resource_key"],
            **base,
            "error": f"{type(error).__name__}: {error}",
            "message": message,
        }