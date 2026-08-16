# AI Excel Agent

A free, lightweight proof of concept that turns natural-language requests into professional Excel reports using real World Bank Open Data. It uses a deterministic rule-based parser—no LLM, API key, database, or paid service.

## Features

- Detects supported countries, indicators, explicit ranges, and “last X years”
- Retrieves real values directly from the World Bank public API
- Produces an in-memory `.xlsx` with Dashboard, Data, and Sources sheets
- Includes an Excel-native comparison chart and exact source URLs
- Never invents missing values; unavailable observations remain blank
- Limits reports to 10 countries, 30 years, and 500 prompt characters

Supported indicators: GDP, GDP Growth, Population, Inflation, and Life Expectancy.

## Run Locally

```bash
git clone YOUR_REPOSITORY
cd ai-excel-agent
python -m venv venv
```

Windows:

```powershell
venv\Scripts\activate
```

Linux/macOS:

```bash
source venv/bin/activate
```

Then:

```bash
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`.

Run tests with `pytest -q` and use the production server with `gunicorn --timeout 180 app:app` (Gunicorn runs on Linux hosting environments).

## Deploy to Render

1. Push this project to GitHub.
2. Create or sign in to a Render account.
3. Select **New Web Service** and connect the repository.
4. Choose the Python runtime and an available free instance type.
5. Set the build command to `pip install -r requirements.txt`.
6. Set the start command to `gunicorn --timeout 180 app:app`.
7. Add `PYTHON_VERSION` with the value `3.11.11`.
8. Deploy and open the generated public URL.

No environment variables, database, persistent disk, worker, or API key is required. `render.yaml` contains the same configuration for Blueprint deployment.

## Data integrity

All numerical report values originate in the World Bank API response. Missing and partially available values are retained as blank cells. If the API is unavailable or returns no usable observations, the app returns a clear error instead of fallback data.

World Bank is the data provider and does not endorse this application.
