from connectors.base import BaseConnector, ConnectorError
from services.registry import METRICS
from services.worldbank import WorldBankError, fetch_country_data

class WorldBankConnector(BaseConnector):
    name = "World Bank"
    def supports(self, metric): return METRICS.get(metric, {}).get("connector") == "worldbank"
    def metadata(self): return {"name": self.name, "key_required": False}
    def fetch(self, query):
        metric = METRICS[query["metric"]]
        country = query["country"]
        try:
            values, url = fetch_country_data(country["code"], metric["indicator"], query["start_year"], query["end_year"])
        except WorldBankError as exc: raise ConnectorError(str(exc)) from exc
        return {"source": self.name, "metric": metric["label"], "metric_key": query["metric"], "country": country["name"], "unit": metric["unit"], "frequency": "annual", "records": [{"period": year, "value": values.get(year)} for year in range(query["start_year"], query["end_year"] + 1)], "metadata": {"indicator": metric["indicator"], "source_url": url}}
