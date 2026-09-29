SENSITIVE_KEYS = {"authorization","x-api-key","api_key","token","access_token","refresh_token","client_secret","consumer_secret","password","secret"}
def redact(value):
    if isinstance(value,dict):
        return {k:("***REDACTED***" if k.lower() in SENSITIVE_KEYS else redact(v)) for k,v in value.items()}
    if isinstance(value,list): return [redact(v) for v in value]
    return value
