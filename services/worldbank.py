import time

import requests

BASE_URL = "https://api.worldbank.org/v2/country/{country}/indicator/{indicator}"
REQUEST_TIMEOUT = (10, 60)
MAX_ATTEMPTS = 2
REQUEST_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "AI-Excel-Agent/1.0 (World Bank Open Data client)",
}

class WorldBankError(RuntimeError):
    pass

def fetch_country_data(country_code, indicator_code, start_year, end_year, session=requests):
    url = BASE_URL.format(country=country_code, indicator=indicator_code)
    params = {"date": f"{start_year}:{end_year}", "format": "json", "per_page": 100}
    exact_url = requests.Request("GET", url, params=params).prepare().url
    connection_error = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            response = session.get(url, params=params, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            payload = response.json()
            break
        except (requests.Timeout, requests.ConnectionError) as exc:
            connection_error = exc
            if attempt + 1 < MAX_ATTEMPTS:
                time.sleep(0.75)
        except (requests.RequestException, ValueError) as exc:
            raise WorldBankError("The public data source returned an invalid response.") from exc
    else:
        raise WorldBankError(
            "We couldn't connect to the World Bank after two attempts. "
            "Please check your internet connection and try again."
        ) from connection_error
    if not isinstance(payload, list) or len(payload) < 2 or not isinstance(payload[1], list):
        raise WorldBankError("World Bank returned no data for this request.")
    values = {}
    for row in payload[1]:
        try:
            year = int(row.get("date"))
            value = row.get("value")
            values[year] = float(value) if value is not None else None
        except (TypeError, ValueError):
            continue
    return values, exact_url

def fetch_report_data(parsed, session=requests):
    data, urls = {}, []
    for country in parsed.countries:
        values, url = fetch_country_data(country["code"], parsed.indicator_code, parsed.start_year, parsed.end_year, session)
        data[country["name"]] = values
        urls.append(url)
    if not any(value is not None for values in data.values() for value in values.values()):
        raise WorldBankError("World Bank returned no data for this request.")
    return data, urls
