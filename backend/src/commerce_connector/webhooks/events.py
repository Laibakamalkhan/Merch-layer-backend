from dataclasses import dataclass
from typing import Any
@dataclass(slots=True)
class WebhookEvent:
    event_type:str
    payload:Any
