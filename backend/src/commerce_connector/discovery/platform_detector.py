from urllib.parse import urlparse
def detect_platform(url):
    parsed=urlparse(url); host=(parsed.hostname or "").lower(); path=parsed.path.lower()
    if host.endswith(".myshopify.com"): return "shopify",1.0
    if "/wp-json/wc/" in path: return "woocommerce",1.0
    if "sellingpartnerapi" in host: return "amazon",1.0
    if "/rest/v1/" in path or "/rest/v1" in path: return "adobe_commerce",0.5
    return None,0.0
