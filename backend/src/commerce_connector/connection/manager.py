class ConnectionManager:
    def __init__(self):
        self._connections = {}
    def add(self, connection):
        self._connections[connection.connection_id] = connection
        return connection
    def remove(self, connection_id):
        self._connections.pop(connection_id, None)
    def get(self, connection_id):
        return self._connections[connection_id]
    def list(self):
        return list(self._connections.values())
