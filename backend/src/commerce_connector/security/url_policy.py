from .ssrf import assert_safe_public_url
class URLPolicy:
    def __init__(self, allow_private_networks=False): self.allow_private_networks=allow_private_networks
    def validate(self,url): assert_safe_public_url(url,self.allow_private_networks)
