from dataclasses import dataclass
@dataclass(slots=True)
class ProxyConfig:
    url: str | None = None
