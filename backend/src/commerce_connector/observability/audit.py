from commerce_connector.security.redaction import redact
class AuditSink:
    def write(self,event): print(redact(event))
