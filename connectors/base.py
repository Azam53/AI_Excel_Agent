from abc import ABC, abstractmethod

class ConnectorError(RuntimeError): pass

class BaseConnector(ABC):
    name = ""
    @abstractmethod
    def supports(self, metric): pass
    @abstractmethod
    def fetch(self, query): pass
    def normalize(self, response): return response
    @abstractmethod
    def metadata(self): pass
    def status(self): return {"name": self.name, "available": True, "message": "Connected"}
