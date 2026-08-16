import re
from dataclasses import dataclass
from datetime import date

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
