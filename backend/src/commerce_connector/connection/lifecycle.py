from commerce_connector.core.enums import ConnectionStatus
def activate(connection):
    connection.status = ConnectionStatus.ACTIVE
    return connection
def disable(connection):
    connection.status = ConnectionStatus.DISABLED
    return connection
def fail(connection):
    connection.status = ConnectionStatus.FAILED
    return connection
