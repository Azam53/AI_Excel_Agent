from connectors.worldbank import WorldBankConnector
from connectors.fred import FredConnector
from connectors.data_gov_india import DataGovIndiaConnector
from services.registry import METRICS

class SourceRouter:
    def __init__(self, connectors=None):
        self.connectors = connectors or {"worldbank": WorldBankConnector(), "fred": FredConnector(), "data_gov_india": DataGovIndiaConnector()}
    def route(self, metric):
        connector_name = METRICS.get(metric, {}).get("connector")
        if not connector_name or connector_name not in self.connectors: raise ValueError(f"No connector registered for {metric}.")
        return connector_name, self.connectors[connector_name]
    def statuses(self): return [connector.status() for connector in self.connectors.values()]
