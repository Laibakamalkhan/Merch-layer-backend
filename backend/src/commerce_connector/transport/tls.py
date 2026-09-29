from dataclasses import dataclass
@dataclass(slots=True)
class TLSConfig:
    verify: bool = True
    client_cert: str | None = None
