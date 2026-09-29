from urllib.parse import urljoin
def join_url(base_url, path):
    if path.startswith(("http://","https://")):
        return path
    return urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
