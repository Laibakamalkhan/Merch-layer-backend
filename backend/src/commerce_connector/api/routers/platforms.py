from fastapi import APIRouter, Depends, HTTPException

from commerce_connector.api.deps import get_service

router = APIRouter(prefix="/platforms", tags=["Platforms"])


def _availability(service):
    by_platform = {}
    for record in service.manifest_factory.repository.discover():
        manifest = record.manifest
        resources = list(manifest.resources or [])
        # A certified manifest with at least one resource is connectable.
        by_platform[manifest.platform] = {
            "connectable": bool(resources),
            "availability": "available" if resources else "coming_soon",
            "manifest_id": manifest.id,
            "resource_count": len(resources),
            "resources": resources,
        }
        # Runtime isi manifest ke connection_fields se credentials jodta hai, isliye UI ko bhi yahi fields do
        # (warna DB mein purani fields ho to form aur backend match nahi karte).
        fields = [f.model_dump(mode="json") for f in (manifest.connection_fields or [])]
        if fields:
            by_platform[manifest.platform]["connection_fields"] = fields
    return by_platform


@router.get("")
def list_platforms(service=Depends(get_service)):
    availability = _availability(service)
    items = []
    for platform in service.db.list_platforms():
        info = availability.get(platform["code"], {
            "connectable": False,
            "availability": "coming_soon",
            "manifest_id": None,
            "resource_count": 0,
            "resources": [],
        })
        items.append({**platform, **info})
    return {"items": items}


@router.get("/{platform_code}")
def get_platform(platform_code: str, service=Depends(get_service)):
    try:
        platform = service.db.get_platform_by_code(platform_code)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    info = _availability(service).get(platform_code, {
        "connectable": False,
        "availability": "coming_soon",
        "manifest_id": None,
        "resource_count": 0,
        "resources": [],
    })
    return {**platform, **info}
