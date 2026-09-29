def classify_status(status_code):
    if status_code in {401,403}: return "auth"
    if status_code == 429: return "rate_limit"
    if 500 <= status_code <= 599: return "server"
    if 400 <= status_code <= 499: return "client"
    return "success"
