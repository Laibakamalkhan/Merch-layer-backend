from dataclasses import dataclass, field
from typing import Any
@dataclass
class RuntimeSession:
    metadata: dict[str,Any] = field(default_factory=dict)
