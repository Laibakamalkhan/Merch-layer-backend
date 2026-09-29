from dataclasses import dataclass
@dataclass(slots=True)
class TimeoutConfig:
    seconds: float = 60.0
