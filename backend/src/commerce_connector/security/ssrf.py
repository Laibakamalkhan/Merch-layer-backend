import ipaddress, socket
from urllib.parse import urlparse
from commerce_connector.core.exceptions import SecurityError

def assert_safe_public_url(url, allow_private_networks=False):
    parsed = urlparse(url)
    if parsed.scheme not in {"https","http"}: raise SecurityError(f"Unsupported URL scheme: {parsed.scheme}")
    hostname = parsed.hostname
    if not hostname: raise SecurityError("URL has no hostname.")
    if allow_private_networks:return
    if hostname.lower() in {"localhost","localhost.localdomain"}: raise SecurityError("Localhost targets are blocked.")
    def blocked(ip_text):
        ip = ipaddress.ip_address(ip_text)
        return any([ip.is_private,ip.is_loopback,ip.is_link_local,ip.is_multicast,ip.is_reserved,ip.is_unspecified])
    try:
        if blocked(hostname): raise SecurityError("Private/local target is blocked.")
    except ValueError: pass
    try: addresses = socket.getaddrinfo(hostname,None)
    except socket.gaierror:return
    for address in addresses:
        ip_text = address[4][0]
        if blocked(ip_text): raise SecurityError(f"Hostname resolves to blocked IP: {ip_text}")
