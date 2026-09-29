from fastapi import APIRouter, Depends, HTTPException

from commerce_connector.api.deps import get_service

router = APIRouter(tags=["Health"])


@router.get("/health")
def health():
    """Liveness: the server process is up. Never touches the database."""
    return {"status": "ok"}


@router.get("/health/ready")
def readiness(service=Depends(get_service)):
    """Readiness: the database is reachable. 503 when it is not configured or down."""
    try:
        return {"status": "ok", "database": service.health()}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database not reachable: {type(exc).__name__}") from exc
