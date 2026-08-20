import re
from dataclasses import dataclass
from datetime import date
from services.registry import METRICS

MAX_COUNTRIES = 10
MAX_YEARS = 30

COUNTRIES = [
    ("United Arab Emirates", "ARE", ["united arab emirates", "uae"]),
    ("United States", "USA", ["united states", "usa", "america", "us"]),
    ("United Kingdom", "GBR", ["united kingdom", "britain", "uk"]),
    ("Saudi Arabia", "SAU", ["saudi arabia", "saudi"]),
    ("South Korea", "KOR", ["south korea"]),
    ("India", "IND", ["india"]), ("China", "CHN", ["china"]),
    ("Japan", "JPN", ["japan"]), ("Germany", "DEU", ["germany"]),
    ("France", "FRA", ["france"]), ("Australia", "AUS", ["australia"]),
    ("Canada", "CAN", ["canada"]), ("Maldives", "MDV", ["maldives"]),
    ("Qatar", "QAT", ["qatar"]), ("Singapore", "SGP", ["singapore"]),
    ("Brazil", "BRA", ["brazil"]), ("Russia", "RUS", ["russia"]),
    ("Indonesia", "IDN", ["indonesia"]), ("Malaysia", "MYS", ["malaysia"]),
    ("Thailand", "THA", ["thailand"]),
]

INDICATORS = [
    ("GDP Growth", "NY.GDP.MKTP.KD.ZG", ["gdp growth", "economic growth", "growth rate"], "percent"),
    ("Life Expectancy", "SP.DYN.LE00.IN", ["life expectancy", "average lifespan", "lifespan"], "years"),
    ("Inflation", "FP.CPI.TOTL.ZG", ["inflation", "consumer price", "cpi"], "percent"),
    ("Population", "SP.POP.TOTL", ["population growth", "population", "people"], "population"),
    ("GDP", "NY.GDP.MKTP.CD", ["gross domestic product", "economy size", "gdp"], "currency"),
]

class ParseError(ValueError):
    pass

@dataclass(frozen=True)
class ParsedRequest:
    countries: list
    indicator_name: str
    indicator_code: str
    value_type: str
    start_year: int
    end_year: int
    chart_requested: bool

def _contains(text, alias):
    return re.search(r"(?<![a-z])" + re.escape(alias) + r"(?:'s)?(?![a-z])", text) is not None

def parse_prompt(prompt, current_year=None):
    if not isinstance(prompt, str) or not prompt.strip():
        raise ParseError("Please enter a data request.")
    if len(prompt) > 500:
        raise ParseError("Please keep your request under 500 characters.")
    text = prompt.lower().replace("’", "'")
    found = []
    for name, code, aliases in COUNTRIES:
        if any(_contains(text, alias) for alias in aliases):
            found.append({"name": name, "code": code})
    if not found:
        raise ParseError("No country detected. Please include at least one supported country.")
    if len(found) > MAX_COUNTRIES:
        raise ParseError("A report can include at most 10 countries.")

    indicator = next((item for item in INDICATORS if any(_contains(text, k) for k in item[2])), None)
    if not indicator:
        raise ParseError("Unsupported indicator. This demo supports GDP, GDP Growth, Population, Inflation and Life Expectancy.")

    now = current_year or date.today().year
    match = re.search(r"(?:from\s+)?(19\d{2}|20\d{2})\s*(?:-|–|to)\s*(19\d{2}|20\d{2})", text)
    if not match:
        match = re.search(r"between\s+(19\d{2}|20\d{2})\s+and\s+(19\d{2}|20\d{2})", text)
    recent = re.search(r"(?:last|past)\s+(\d{1,2})\s+years?", text)
    if match:
        start, end = map(int, match.groups())
    elif recent:
        count = int(recent.group(1))
        start, end = now - count + 1, now
    else:
        start, end = now - 9, now
    if start > end:
        raise ParseError("The starting year must be before the ending year.")
    if start < 1960 or end > now + 1:
        raise ParseError(f"Choose years between 1960 and {now + 1}.")
    if end - start + 1 > MAX_YEARS:
        raise ParseError("A report can cover at most 30 years.")
    name, code, _, value_type = indicator
    return ParsedRequest(found, name, code, value_type, start, end, "chart" in text or len(found) > 1)

def parse_request(prompt, current_year=None, require_complete=True):
    if not isinstance(prompt, str) or not prompt.strip():
        raise ParseError("Please enter a data request.")
    if len(prompt) > 500:
        raise ParseError("Please keep your request under 500 characters.")
    text = prompt.lower().replace("’", "'")
    detected_countries = []
    for name, code, aliases in COUNTRIES:
        positions = [match.start() for alias in aliases if (match := re.search(r"(?<![a-z])" + re.escape(alias) + r"(?:'s)?(?![a-z])", text))]
        if positions: detected_countries.append((min(positions), {"name": name, "code": code}))
    countries = [country for _, country in sorted(detected_countries, key=lambda item: item[0])]
    detected_metrics = []
    masked = text
    for key, config in METRICS.items():
        keywords = config["keywords"]
        if key == "brent_crude" and "wti" in text:
            keywords = [keyword for keyword in keywords if "brent" in keyword]
        matches = [(match.start(), keyword) for keyword in keywords if (match := re.search(r"(?<![a-z])" + re.escape(keyword) + r"(?![a-z])", masked))]
        if matches:
            detected_metrics.append((min(position for position, _ in matches), key))
            for keyword in keywords:
                if _contains(masked, keyword): masked = re.sub(r"(?<![a-z])" + re.escape(keyword) + r"(?![a-z])", " ", masked)
    metric_keys = [key for _, key in sorted(detected_metrics, key=lambda item: item[0])]
    now = current_year or date.today().year
    match = re.search(r"(?:from\s+)?(19\d{2}|20\d{2})\s*(?:-|–|to)\s*(19\d{2}|20\d{2})", text) or re.search(r"between\s+(19\d{2}|20\d{2})\s+and\s+(19\d{2}|20\d{2})", text)
    recent = re.search(r"(?:last|past)\s+(\d{1,2})\s+years?", text)
    after = re.search(r"(?:only\s+)?(?:show\s+)?(?:data\s+)?after\s+(19\d{2}|20\d{2})", text)
    if match: start, end = map(int, match.groups())
    elif recent: start, end = now - int(recent.group(1)) + 1, now
    elif after: start, end = int(after.group(1)) + 1, None
    else: start = end = None
    if require_complete:
        if not metric_keys: raise ParseError("I need a measurable topic before I can build the report.")
        if not countries and any(METRICS[key]["connector"] == "worldbank" for key in metric_keys): raise ParseError("I recognized the metric, and I still need a country for that public dataset.")
        if start is None: start, end = now - 9, now
    if start is not None and end is not None:
        if start > end: raise ParseError("The starting year must be before the ending year.")
        if start < 1960 or end > now + 1: raise ParseError(f"Choose years between 1960 and {now + 1}.")
        if end - start + 1 > 30: raise ParseError("A report can cover at most 30 years.")
    if len(countries) > 5: raise ParseError("A conversational report can include at most 5 countries.")
    if len(metric_keys) > 5: raise ParseError("A report can include at most 5 metrics.")
    return {"countries": countries, "metrics": metric_keys, "start_year": start, "end_year": end}

def merge_context(previous, update, current_year=None):
    now = current_year or date.today().year
    previous = previous or {}
    countries = list(previous.get("countries", []))
    metrics = list(previous.get("metrics", []))
    for country in update.get("countries", []):
        if country not in countries: countries.append(country)
    for metric in update.get("metrics", []):
        if metric not in metrics: metrics.append(metric)
    start = update.get("start_year") if update.get("start_year") is not None else previous.get("start_year")
    end = update.get("end_year") if update.get("end_year") is not None else previous.get("end_year")
    if start is None: start = now - 9
    if end is None: end = previous.get("end_year", now)
    if not metrics: raise ParseError("I need a measurable topic before I can build the report.")
    if not countries and any(METRICS[key]["connector"] == "worldbank" for key in metrics): raise ParseError("I recognized the metric, and I still need a country for that public dataset.")
    if len(countries) > 5 or len(metrics) > 5 or end - start + 1 > 30:
        raise ParseError("Limit requests to 5 countries, 5 metrics and 30 years.")
    return {"countries": countries, "metrics": metrics, "start_year": start, "end_year": end}

def should_extend_context(message, previous, update):
    """Return True only for clearly incremental or incomplete follow-up requests."""
    if not previous:
        return False
    text = (message or "").strip().lower()
    follow_up = re.search(r"^(?:now\s+)?(?:add|include|also|only|after|before|keep|remove)\b", text) or re.search(r"\btoo\s*$", text)
    if follow_up:
        return True
    metrics = update.get("metrics", [])
    countries = update.get("countries", [])
    is_complete_request = bool(metrics) and (bool(countries) or all(METRICS[key]["connector"] != "worldbank" for key in metrics))
    return not is_complete_request
