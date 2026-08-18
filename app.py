import os
import re
import secrets
import threading
import time
from flask import Flask, jsonify, render_template, request, send_file, session
from services.parser import ParseError, merge_context, parse_prompt, parse_request
from services.worldbank import WorldBankError, fetch_report_data
from services.excel_generator import generate_multi_workbook, generate_workbook
from services.csv_generator import generate_csv
from services.data_merger import merge_results, series_label
from services.data_normalizer import normalize_result
from services.query_planner import build_plan, execute_plan
from services.registry import METRICS
from services.source_router import SourceRouter

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024
app.secret_key = os.getenv("FLASK_SECRET_KEY") or secrets.token_hex(32)
ARTIFACT_TTL = 15 * 60
artifacts = {}
artifact_lock = threading.Lock()

@app.get("/")
def index(): return render_template("index.html")

def filename_for(parsed):
    names = "_".join(c["name"] for c in parsed.countries)
    raw = f"{parsed.indicator_name}_{names}_{parsed.start_year}_{parsed.end_year}.xlsx"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", raw).strip("._")

def safe_report_name(context, extension):
    metrics = "_".join(METRICS[key]["label"] for key in context["metrics"])
    raw = f'{metrics}_{context["start_year"]}_{context["end_year"]}.{extension}'
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", raw).strip("._")

def store_artifacts(excel, csv_file, context):
    token = secrets.token_urlsafe(24); now = time.time()
    with artifact_lock:
        for key in [key for key, value in artifacts.items() if now - value["created"] > ARTIFACT_TTL]: artifacts.pop(key, None)
        if len(artifacts) >= 100:
            artifacts.pop(min(artifacts, key=lambda key: artifacts[key]["created"]), None)
        artifacts[token] = {"created": now, "excel": excel.getvalue(), "csv": csv_file.getvalue(), "context": context}
    return token

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

@app.get("/api/sources")
def source_status(): return jsonify({"sources": SourceRouter().statuses()})

@app.post("/api/chat")
def chat():
    try:
        payload = request.get_json(silent=True) or {}; message = payload.get("message", "")
        update = parse_request(message, require_complete=False)
        context = merge_context(session.get("conversation"), update)
        plan = build_plan(context); raw_results, errors = execute_plan(plan); results = []
        for raw_result in raw_results:
            if any(row["value"] is not None for row in raw_result["records"]):
                results.append(normalize_result(raw_result))
            else:
                errors.append({"source": raw_result["source"], "metric": raw_result["metric_key"], "country": raw_result.get("country"), "error": "No observations were available for the requested period."})
        if not results:
            detail = errors[0]["error"] if errors else "No source returned usable data."
            return jsonify({"success": False, "error": detail, "sources": errors}), 502
        merged = merge_results(results, context["start_year"], context["end_year"])
        excel = generate_multi_workbook(context, results, merged, errors); csv_file = generate_csv(merged); token = store_artifacts(excel, csv_file, context)
        session["conversation"] = context
        successes = [{"name": result["source"], "metric": series_label(result), "status": "success", "aggregation": result["metadata"].get("aggregation")} for result in results]
        failures = [{"name": error["source"], "metric": METRICS.get(error["metric"], {}).get("label", error["metric"]), "status": "unavailable", "message": error["error"]} for error in errors]
        source_count = len({result["source"] for result in results}); dataset_count = len(results)
        summary = f'I combined {dataset_count} data series from {source_count} source{"s" if source_count != 1 else ""} for {context["start_year"]}–{context["end_year"]}.'
        if any(result["metadata"].get("aggregation") for result in results): summary += " Higher-frequency FRED observations were converted to documented annual averages."
        if errors: summary += " The report uses all available datasets; unavailable sources are listed below."
        return jsonify({"success": True, "message": summary, "context": {"countries": [c["name"] for c in context["countries"]], "metrics": [METRICS[m]["label"] for m in context["metrics"]], "start_year": context["start_year"], "end_year": context["end_year"]}, "sources": successes + failures, "preview": merged["rows"][:10], "columns": merged["columns"], "data": merged["rows"], "excel_available": True, "csv_available": True, "download_token": token})
    except ParseError as exc: return jsonify({"success": False, "error": str(exc)}), 400
    except Exception:
        app.logger.exception("Chat request failed"); return jsonify({"success": False, "error": "We couldn't build this report. Please try again."}), 500

@app.get("/api/download/<token>/<file_type>")
def download_report(token, file_type):
    if file_type not in {"excel", "csv"}: return jsonify({"error": "Unsupported download type."}), 404
    with artifact_lock: artifact = artifacts.get(token)
    if not artifact or time.time() - artifact["created"] > ARTIFACT_TTL: return jsonify({"error": "This download has expired. Please run the query again."}), 404
    from io import BytesIO
    extension = "xlsx" if file_type == "excel" else "csv"; mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if file_type == "excel" else "text/csv"
    return send_file(BytesIO(artifact[file_type]), as_attachment=True, download_name=safe_report_name(artifact["context"], extension), mimetype=mimetype)

@app.post("/api/chat/reset")
def reset_chat(): session.pop("conversation", None); return jsonify({"success": True})

@app.errorhandler(413)
def too_large(_): return jsonify({"error": "Request is too large."}), 413

if __name__ == "__main__": app.run(debug=True)
