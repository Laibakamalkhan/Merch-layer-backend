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
                "provider": "gemini",
                "backend_model": settings.gemini_model,
                "supports_reasoning": True,
                "supports_files": True,
                "supports_dashboards": True,
                "available": bool(settings.gemini_api_key),
            }
        ],
    }
