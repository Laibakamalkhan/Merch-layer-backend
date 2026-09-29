from enum import Enum
class ExecutionState(str, Enum):
    PENDING="pending"; RUNNING="running"; COMPLETED="completed"; FAILED="failed"
