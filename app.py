import re
from flask import Flask, jsonify, render_template, request, send_file
from services.parser import ParseError, parse_prompt
from services.worldbank import WorldBankError, fetch_report_data
from services.excel_generator import generate_workbook

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024

@app.get("/")
def index(): return render_template("index.html")

def filename_for(parsed):
    names = "_".join(c["name"] for c in parsed.countries)
    raw = f"{parsed.indicator_name}_{names}_{parsed.start_year}_{parsed.end_year}.xlsx"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", raw).strip("._")

@app.post("/api/generate")
def generate():
    try:
        payload = request.get_json(silent=True) or {}
        parsed = parse_prompt(payload.get("prompt", ""))
        data, urls = fetch_report_data(parsed)
        workbook = generate_workbook(parsed, data, urls)
        available = [(year, value) for values in data.values() for year, value in values.items() if value is not None]
        response = send_file(workbook, as_attachment=True, download_name=filename_for(parsed), mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response.headers["X-Report-Indicator"] = parsed.indicator_name
        response.headers["X-Report-Countries"] = ", ".join(country["name"] for country in parsed.countries)
        response.headers["X-Report-Period"] = f"{parsed.start_year}-{parsed.end_year}"
        response.headers["X-Report-Latest-Year"] = str(max(year for year, _ in available))
        response.headers["X-Report-Records"] = str(len(available))
        return response
    except (ParseError, WorldBankError) as exc:
        return jsonify({"error": str(exc)}), 400 if isinstance(exc, ParseError) else 502
    except Exception:
        app.logger.exception("Report generation failed")
        return jsonify({"error": "We couldn't generate the report. Please try again."}), 500

@app.errorhandler(413)
def too_large(_): return jsonify({"error": "Request is too large."}), 413

if __name__ == "__main__": app.run(debug=True)
