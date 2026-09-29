from commerce_connector.connection.factory import ConnectionManifestFactory
from commerce_connector.core.connector import UniversalCommerceConnector
from .resource_executor import execute_resource

async def execute_connection(connection, *, transport=None, allow_private_networks=False):
    manifest=ConnectionManifestFactory.build(connection)
    results=[]
    async with UniversalCommerceConnector(
        manifest,transport=transport,allow_private_networks=allow_private_networks
    ) as connector:
        for resource in connection.resources:
            results.append(await execute_resource(connector,resource))
    return {
        "connection_id":connection.connection_id,
        "name":connection.name,
        "manifest_id":connection.manifest_id,
        "resources":results,
    }
