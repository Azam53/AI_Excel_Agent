import os
from collections import defaultdict
from datetime import datetime
import requests
from connectors.base import BaseConnector, ConnectorError
from services.registry import METRICS

class FredConnector(BaseConnector):
    name = "FRED"
    def __init__(self, api_key=None, session=requests): self.api_key = api_key if api_key is not None else os.getenv("FRED_API_KEY", ""); self.session = session
    def supports(self, metric): return METRICS.get(metric, {}).get("connector") == "fred"
    def metadata(self): return {"name": self.name, "key_required": True}
    def status(self): return {"name": self.name, "available": bool(self.api_key), "message": "Connected" if self.api_key else "API key not configured"}
    def fetch(self, query):
        if not self.api_key: raise ConnectorError("FRED unavailable because no API key is configured.")
        config = METRICS[query["metric"]]
        url = "https://api.stlouisfed.org/fred/series/observations"
        params = {"series_id": config["series"], "api_key": self.api_key, "file_type": "json", "observation_start": f'{query["start_year"]}-01-01', "observation_end": f'{query["end_year"]}-12-31'}
        try:
            response = self.session.get(url, params=params, timeout=(10, 60)); response.raise_for_status(); payload = response.json()
        except (requests.RequestException, ValueError) as exc: raise ConnectorError("FRED could not return this dataset.") from exc
        annual = defaultdict(list)
        for row in payload.get("observations", []):
            try: annual[datetime.strptime(row["date"], "%Y-%m-%d").year].append(float(row["value"]))
            except (KeyError, ValueError, TypeError): continue
        records = [{"period": year, "value": (sum(annual[year]) / len(annual[year]) if annual[year] else None)} for year in range(query["start_year"], query["end_year"] + 1)]
        source_url = requests.Request("GET", url, params={k:v for k,v in params.items() if k != "api_key"}).prepare().url
        return {"source": self.name, "metric": config["label"], "metric_key": query["metric"], "country": None, "unit": config["unit"], "frequency": "annual", "records": records, "metadata": {"series": config["series"], "source_url": source_url, "aggregation": "Annual average of available observations"}}
