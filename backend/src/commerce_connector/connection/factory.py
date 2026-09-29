from commerce_connector.manifests.loader import load_manifest_source
from commerce_connector.manifests.resolver import apply_connection_inputs
from commerce_connector.manifests.schema import PlatformManifest

class ConnectionManifestFactory:
    @staticmethod
    def build(connection):
        source = load_manifest_source(connection.manifest_path)
        runtime = apply_connection_inputs(source, connection.inputs)
        return PlatformManifest.model_validate(runtime)
