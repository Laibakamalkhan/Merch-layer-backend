from pathlib import Path
from commerce_connector.manifests.compiler import compile_manifest
ROOT=Path(__file__).resolve().parents[3]
def test_shopify_directory_manifest_compiles():
    manifest=compile_manifest(ROOT/"manifests"/"certified"/"shopify")
    assert manifest.platform=="shopify"
    assert "orders" in manifest.resources
    assert "products" in manifest.resources
