from .schema import PlatformManifest
def validate_manifest(data: dict) -> PlatformManifest:
    return PlatformManifest.model_validate(data)
