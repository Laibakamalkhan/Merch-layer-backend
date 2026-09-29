from typing import Any
from .exceptions import ConnectorError

class Registry:
    def __init__(self):
        self._items: dict[str, type[Any]] = {}

    def register(self, name, cls):
        key = name.strip().lower()
        if not key:
            raise ConnectorError("Registry key cannot be empty.")
        self._items[key] = cls

    def get(self, name):
        key = name.strip().lower()
        try:
            return self._items[key]
        except KeyError as exc:
            raise ConnectorError(
                f"Component '{name}' is not registered. Available: {sorted(self._items)}"
            ) from exc

    def decorator(self, name):
        def wrap(cls):
            self.register(name, cls)
            return cls
        return wrap

    def names(self):
        return sorted(self._items)

auth_registry = Registry()
protocol_registry = Registry()
pagination_registry = Registry()
