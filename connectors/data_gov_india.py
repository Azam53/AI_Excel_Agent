import os
from connectors.base import BaseConnector, ConnectorError
from services.registry import DATA_GOV_RESOURCES

class DataGovIndiaConnector(BaseConnector):
    name = "India Open Data"
    def __init__(self, api_key=None): self.api_key = api_key if api_key is not None else os.getenv("DATA_GOV_IN_API_KEY", "")
    def supports(self, metric): return metric in DATA_GOV_RESOURCES
    def metadata(self): return {"name": self.name, "key_required": True, "resources": list(DATA_GOV_RESOURCES)}
    def status(self):
        configured = bool(self.api_key and DATA_GOV_RESOURCES)
        return {"name": self.name, "available": configured, "message": "Connected" if configured else "API key or demo resource not configured"}
    def fetch(self, query): raise ConnectorError("India Open Data has no configured demo resource for this metric.")
