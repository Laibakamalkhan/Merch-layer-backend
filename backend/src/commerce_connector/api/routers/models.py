from __future__ import annotations

from fastapi import APIRouter, Depends

from commerce_connector.api.auth import CurrentUser, get_current_user
from commerce_connector.api.deps import get_api_settings

router = APIRouter(prefix="/models", tags=["AI Models"])


@router.get("")
def models(current_user: CurrentUser = Depends(get_current_user)):
    settings = get_api_settings()
    return {
        "default": "merchlayer-2.0",
        "items": [
            {
                "id": "merchlayer-2.0",
                "name": "Merchlayer 2.0",
                "provider": settings.llm_provider,
                "backend_model": settings.groq_model,
                "supports_reasoning": True,
                "supports_files": True,
                "supports_dashboards": True,
                "available": bool(settings.groq_api_key),
                "embedding_provider": settings.embedding_provider,
                "embedding_model": settings.ollama_embedding_model,
                "embedding_dimensions": settings.embedding_dimensions,
            }
        ],
    }
