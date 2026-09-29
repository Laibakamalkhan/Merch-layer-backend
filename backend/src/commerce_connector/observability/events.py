from dataclasses import dataclass
from typing import Any
@dataclass(slots=True)
class ConnectorEvent:
    name:str
    fields:dict[str,Any]
