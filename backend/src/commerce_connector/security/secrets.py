from abc import ABC, abstractmethod
class SecretStore(ABC):
    @abstractmethod
    def put(self,key,value): ...
    @abstractmethod
    def get(self,key): ...
class InMemorySecretStore(SecretStore):
    """Development/testing only. Use Vault/cloud secret manager in production."""
    def __init__(self): self.values={}
    def put(self,key,value): self.values[key]=value
    def get(self,key): return self.values[key]
