from .loader import load_manifest_source
from .schema import PlatformManifest


def compile_manifest(source):
    """Manifest ko PlatformManifest mein badalta hai.

    FIX #3: pehle yeh sirf file/folder path leta tha, lekin service.test_connection aur
    orchestrator runtime par ek dict (credentials ke saath) pass karte hain. Is wajah se
    har connection test 'TypeError ... not dict' se fail hota tha. Ab dict bhi chalta hai.
    """
    if isinstance(source, PlatformManifest):
        return source
    if isinstance(source, dict):
        return PlatformManifest.model_validate(source)
    return PlatformManifest.model_validate(load_manifest_source(source))
