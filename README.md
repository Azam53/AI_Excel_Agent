# AI Data Consultant

A lightweight conversational public-data assistant that turns rule-parsed questions into merged, analysis-ready Excel and CSV reports. It supports multiple metrics, multiple countries, follow-up prompts and transparent source metadata without an LLM, database or paid service.

## Data sources

- **World Bank** — always available without a key: GDP, GDP Growth, Population, Inflation, Life Expectancy and Unemployment.
- **FRED** — optional `FRED_API_KEY`: Brent crude, WTI crude, US Federal Funds Rate and US CPI. Higher-frequency observations are documented and converted to annual averages.
- **India Open Data** — optional connector foundation for explicitly registered data.gov.in resources. No arbitrary resource IDs or URLs are accepted.

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

Optional local configuration can be copied from `.env.example`. Set values in your shell or hosting environment; the app works with World Bank alone.

```env
FRED_API_KEY=
DATA_GOV_IN_API_KEY=
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
