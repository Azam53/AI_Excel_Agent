# AI Data Consultant

A lightweight conversational public-data assistant that turns rule-parsed questions into merged, analysis-ready Excel and CSV reports. It supports multiple metrics, multiple countries, follow-up prompts and transparent source metadata without an LLM, database or paid service.

## Data sources

- **World Bank** — always available without a key: GDP, GDP Growth, Population, Inflation, Life Expectancy and Unemployment.
- **FRED** — optional `FRED_API_KEY`: Brent crude, WTI crude, US Federal Funds Rate and US CPI. Higher-frequency observations are documented and converted to annual averages.
- **India Open Data** — optional connector foundation for explicitly registered data.gov.in resources. No arbitrary resource IDs or URLs are accepted.
- **Web Search** — optional Tavily API for questions outside registered datasets. Search snippets remain attributed source listings, not verified numerical answers.

If an optional connector is unavailable, the app returns available datasets and clearly lists the omitted source. It never invents missing observations.

## Architecture

```text
Question → rule-based parser → query planner → source router
         → registered connectors → normalize → merge by year
         → chat preview → in-memory Excel / CSV downloads
```

Conversation context is stored in the signed Flask session. Generated files use random, short-lived in-memory tokens and expire after 15 minutes. Limits are 5 countries, 5 metrics, 30 years, 10 preview rows and 4 charts.

## Run locally

```powershell
git clone https://github.com/Azam53/AI_Excel_Agent.git
cd AI_Excel_Agent
python -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`.

Optional local configuration can be copied from `.env.example`. Local `.env` values are loaded automatically; the app works with World Bank alone.

```env
FRED_API_KEY=
DATA_GOV_IN_API_KEY=
WEB_SEARCH_PROVIDER=
WEB_SEARCH_API_KEY=
FLASK_SECRET_KEY=replace-with-a-long-random-value
```

Run tests:

```powershell
python -m pytest -q
```

## Conversation examples

```text
Compare India and UAE GDP and inflation from 2015 to 2025
Compare India's GDP with Brent crude oil prices from 2015 to 2025
Show India's unemployment and GDP growth from 2015 to 2025
```

Limited rule-based follow-ups are supported:

```text
Add Saudi Arabia
Add inflation too
Only show data after 2020
```

“After 2020” consistently means 2021 onward.

## API

- `POST /api/chat` — plan, fetch, merge and return a chat response and download token.
- `POST /api/chat/plan` — read-only routing preview used by the processing animation; does not fetch datasets or search.
- `GET /api/download/<token>/excel` — download the combined workbook.
- `GET /api/download/<token>/csv` — download combined CSV data.
- `POST /api/chat/reset` — clear conversation context.
- `GET /api/sources` — connector availability.
- `POST /api/generate` — preserved legacy single-metric Excel endpoint.

## Deploy to Render

The included `render.yaml` deploys one free Python web service with no database or disk.

1. Push the repository to GitHub.
2. In Render, create a **New Web Service** and connect the repository.
3. Use build command `pip install -r requirements.txt`.
4. Use start command `gunicorn --timeout 180 app:app`.
5. Choose the available free instance type.
6. Set `FLASK_SECRET_KEY` to a long random value.
7. Optionally set `FRED_API_KEY` and `DATA_GOV_IN_API_KEY`.
8. Deploy and open the generated `onrender.com` URL.

`PYTHON_VERSION=3.11.11` is already declared in `render.yaml`. No OpenAI key, paid API, authentication, Redis, Docker, worker, database or persistent storage is required.

World Bank, FRED and data.gov.in do not endorse this demonstration.

## Optional Internet Search Fallback

Structured metrics always take priority: GDP and life expectancy use World Bank; Brent uses FRED. A connector outage does not silently switch historical data to web values. Unsupported informational topics, explanations and forecasts become clearly labeled web research. Mixed questions return both sections, with separate downloads. No LLM, crawler, browser automation or search-result HTML scraping is used.

The isolated adapter in `connectors/web_search.py` uses [Tavily Search](https://docs.tavily.com/documentation/api-reference/endpoint/search). As checked on September 7, 2026, [Tavily pricing](https://www.tavily.com/pricing) advertises 1,000 free API credits per month without a credit card. Basic search uses one credit. Free-tier eligibility, limits and prices can change; check the provider before enabling it. The authenticated mode requires an API key; no new SDK or paid dependency is needed.

1. Create an account at [Tavily](https://app.tavily.com) and obtain an API key.
2. Copy `.env.example` to `.env` for local development, then set `WEB_SEARCH_PROVIDER=tavily` and `WEB_SEARCH_API_KEY` to your key.
3. Restart the application. In authenticated mode, with either setting absent, structured reports still work and research requests explain that search is not configured. Unsupported provider names also report not configured.
4. For Render: **Render Dashboard → Web Service → Environment → Add Environment Variable**. Add both variables there and save/redeploy. Keep `FLASK_SECRET_KEY` stable. Never put actual keys in GitHub, source code, README or `render.yaml`. `.env` is ignored by Git.

Provider responses are normalized to query plus title, URL, snippet, domain, source and optional publication date. Up to 10 candidates are ranked by query-word overlap, explicitly recognized government/academic/institutional authority and recency when present; at most five are shown. Generic `.org` sites receive no authority bonus. This heuristic is a preference, not a verification guarantee. Unknown company domains receive no automatic authority bonus.

The request interpreter and query builder are deterministic, separately replaceable modules. Explicit mixed clauses such as “Show India's GDP and find information about India's AI industry growth” are supported. Country follow-ups such as “What about UAE?” reuse the lightweight web topic. New Chat clears both contexts. The UI's processing steps describe the selected workflow, not streamed provider telemetry. Source status indicates configuration, not a live connectivity probe.

Try:

```text
What is India's AI market size?
What about UAE?
Find the latest information about India's electric vehicle market.
Show India's GDP from 2018 to 2025 and find information about India's AI industry growth.
```

`/api/chat` returns `mode` (`structured`, `web`, or `mixed`). Research lives in `web`, with `status`, `query`, `results`, `message` and an optional separate `download_token`. Missing configuration, provider failure and empty results have distinct statuses and no fabricated observations. A mixed response retains its successful portion and explains failures. The existing structured response fields and `/api/generate` remain compatible. `/api/sources` preserves the existing `sources` list, adding `type` and `status`.

Research Excel contains **Search Results** (Title, Source, Domain, Snippet, Published Date, URL) and **Search Info** (question, query, timestamp, count, provider, interpretation notice). CSV exports only the listing. These files never enter dataset merging or statistical charts. Spreadsheet formula prefixes are neutralized. Downloads retain the existing 15-minute in-memory expiry; Search Again performs a fresh request and consumes provider credits.

Security controls include a 500-character question limit, fixed API endpoint, connect/read timeouts, disabled API redirects, bounded results, HTTP(S)-only source links, rejected credentials/local IPs in links, HTML escaping, and external links with `noopener noreferrer`. Result pages are never fetched by the server. Logs contain routing, provider, result counts and sanitized failures, not keys or authorization headers.

Tests mock search HTTP calls and cover routing, missing configuration, errors, empty results, normalization, ranking, unsafe URLs, mixed requests, context reset, downloads and connector status. Gunicorn runs on Linux (including Render); use Flask locally on Windows. Keep the default single worker because artifact storage is process-local, as in the existing application.

### Keyless demo mode

The [Tavily setup guide](https://tavily.com/agent-setup/SKILL.md) also documents rate-limited keyless Search and Extract. Set `WEB_SEARCH_PROVIDER=tavily-keyless` to opt in; `WEB_SEARCH_API_KEY` can remain empty. The adapter sends `X-Tavily-Access-Mode: keyless` without authorization credentials. A blank provider still disables search. Live keyless search was verified on September 7, 2026; availability and limits may change. Use `tavily` with a key for authenticated access. Restart after changing configuration. Render supports the same provider setting.
