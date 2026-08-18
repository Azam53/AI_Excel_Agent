METRICS = {
    "gdp_growth": {"label": "GDP Growth", "connector": "worldbank", "indicator": "NY.GDP.MKTP.KD.ZG", "unit": "%", "keywords": ["gdp growth", "economic growth", "growth rate"]},
    "life_expectancy": {"label": "Life Expectancy", "connector": "worldbank", "indicator": "SP.DYN.LE00.IN", "unit": "years", "keywords": ["life expectancy", "average lifespan", "lifespan"]},
    "unemployment": {"label": "Unemployment", "connector": "worldbank", "indicator": "SL.UEM.TOTL.ZS", "unit": "%", "keywords": ["unemployment", "unemployment rate", "jobless rate"]},
    "brent_crude": {"label": "Brent Crude Oil", "connector": "fred", "series": "DCOILBRENTEU", "unit": "USD/barrel", "keywords": ["brent crude oil", "brent crude", "brent oil", "brent", "crude oil prices", "crude oil"]},
    "wti_crude": {"label": "WTI Crude Oil", "connector": "fred", "series": "DCOILWTICO", "unit": "USD/barrel", "keywords": ["wti crude oil", "wti crude", "wti oil", "wti"]},
    "federal_funds": {"label": "US Federal Funds Rate", "connector": "fred", "series": "FEDFUNDS", "unit": "%", "keywords": ["us federal funds rate", "federal funds rate", "fed funds rate", "interest rates", "interest rate"]},
    "us_cpi": {"label": "US CPI", "connector": "fred", "series": "CPIAUCSL", "unit": "index", "keywords": ["us cpi", "american cpi"]},
    "inflation": {"label": "Inflation", "connector": "worldbank", "indicator": "FP.CPI.TOTL.ZG", "unit": "%", "keywords": ["inflation", "consumer price"]},
    "population": {"label": "Population", "connector": "worldbank", "indicator": "SP.POP.TOTL", "unit": "people", "keywords": ["population", "people"]},
    "gdp": {"label": "GDP", "connector": "worldbank", "indicator": "NY.GDP.MKTP.CD", "unit": "USD", "keywords": ["gross domestic product", "economy size", "gdp"]},
}

DATA_GOV_RESOURCES = {}
