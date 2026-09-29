class ConnectorError(Exception): pass
class ManifestError(ConnectorError): pass
class AuthenticationError(ConnectorError): pass
class ProtocolError(ConnectorError): pass
class PaginationError(ConnectorError): pass
class DiscoveryError(ConnectorError): pass
class SecurityError(ConnectorError): pass
class CircuitOpenError(ConnectorError): pass
