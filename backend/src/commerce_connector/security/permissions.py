def can_access_connection(tenant_id, connection_tenant_id):
    return connection_tenant_id is None or tenant_id == connection_tenant_id
