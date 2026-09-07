import os
import re
import secrets
import threading
import time
import logging
from datetime import datetime, timezone
from flask import Flask, jsonify, render_template, request, send_file, session
from dotenv import load_dotenv
from services.parser import ParseError, merge_context, parse_prompt, parse_request, should_extend_context
from services.worldbank import WorldBankError, fetch_report_data
from services.excel_generator import generate_multi_workbook, generate_workbook
from services.csv_generator import generate_csv
from services.data_merger import merge_results, series_label
from services.data_normalizer import normalize_result
from services.query_planner import build_plan, execute_plan
from services.registry import METRICS
from services.source_router import SourceRouter
from connectors.web_search import WebSearchConnector, WebSearchError
from services.request_interpreter import interpret_request
from services.search_query_builder import build_search_query
from services.search_export import generate_search_exports

load_dotenv()

app = Flask(__name__)
app.logger.setLevel(logging.INFO)
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
    if context.get('mode') == 'web': return 'Search_Results.' + extension
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

def friendly_error_payload(error, original_message=""):
    detail = str(error)
    error_code = getattr(error, "code", "clarification")
    if error_code == "explanation":
        message = "That’s a useful ‘why’ question. I can show the measured trend from public data, but this rule-based demo cannot reliably determine the causes without broader research. I won’t invent an explanation."
        suggestions = ["Show Japan population for the last 10 years", "Compare Japan population and GDP growth from 2015 to 2025"]
    elif error_code == "forecast":
        message = "That question asks for a forecast. I currently use observed public data only, so I won’t generate future numbers. I can prepare the historical trend instead."
        suggestions = ["Show India GDP for the last 10 years", "Compare India and China GDP growth from 2015 to 2025"]
    elif "measurable topic" in detail:
        message = "I understood that you want a data report. Tell me the measurable topic you want to explore, and I’ll connect it to the right public source."
        suggestions = ["Compare India GDP and inflation from 2015 to 2025", "Show Japan population for the last 10 years", "Compare India GDP with Brent crude oil prices"]
    elif "still need a country" in detail:
        message = "I recognized the topic. Add a country name and I can retrieve the matching World Bank series for you."
        suggestions = ["Show India GDP for the last 10 years", "Compare Germany and France unemployment from 2015 to 2025", "Show Japan life expectancy from 2010 to 2024"]
    elif "starting year" in detail or "Choose years" in detail or "30 years" in detail:
        message = f"I understood the request, but the time period needs a small adjustment. {detail}"
        suggestions = ["Compare India GDP from 2015 to 2025", "Show India inflation for the last 10 years"]
    elif "5 countries" in detail or "5 metrics" in detail:
        message = f"That is a useful comparison, but it is larger than this free demo can process in one report. {detail} Try splitting it into two questions."
        suggestions = ["Compare India, China and USA GDP from 2015 to 2025", "Compare India GDP, inflation and population for the last 10 years"]
    else:
        message = f"I’m close, but I need one more detail before I can create a trustworthy report. {detail}"
        suggestions = ["Compare India and UAE GDP from 2015 to 2025", "Show India's unemployment and GDP growth from 2015 to 2025"]
    return {"success": False, "error": message, "suggestions": suggestions, "can_retry": True, "original_message": original_message}

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

def structured_chat(message):
    try:
        update = parse_request(message, require_complete=False)
        previous = session.get("conversation")
        context_mode = "follow_up" if should_extend_context(message, previous, update) else "new_request"
        context = merge_context(previous if context_mode == "follow_up" else None, update)
        plan = build_plan(context); raw_results, errors = execute_plan(plan); results = []
        app.logger.info('selected_connectors=%s errors=%d', ','.join(sorted({task['source'] for task in plan['tasks']})), len(errors))
        for raw_result in raw_results:
            if any(row["value"] is not None for row in raw_result["records"]):
                results.append(normalize_result(raw_result))
            else:
                errors.append({"source": raw_result["source"], "metric": raw_result["metric_key"], "country": raw_result.get("country"), "error": "No observations were available for the requested period."})
        if not results:
            detail = errors[0]["error"] if errors else "The public sources did not return usable observations for this period."
            return jsonify({"success": False, "error": "I understood your request, but the public data sources could not complete it just now. " + detail + " Your question is still here, so you can retry or choose a shorter period.", "sources": errors, "suggestions": [message, "Compare India GDP from 2020 to 2024"], "can_retry": True}), 502
        merged = merge_results(results, context["start_year"], context["end_year"])
        excel = generate_multi_workbook(context, results, merged, errors); csv_file = generate_csv(merged); token = store_artifacts(excel, csv_file, context)
        session["conversation"] = context
        successes = [{"name": result["source"], "metric": series_label(result), "status": "success", "aggregation": result["metadata"].get("aggregation")} for result in results]
        failures = [{"name": error["source"], "metric": METRICS.get(error["metric"], {}).get("label", error["metric"]), "status": "unavailable", "message": error["error"]} for error in errors]
        source_count = len({result["source"] for result in results}); dataset_count = len(results)
        summary = f'I combined {dataset_count} data series from {source_count} source{"s" if source_count != 1 else ""} for {context["start_year"]}–{context["end_year"]}.'
        if any(result["metadata"].get("aggregation") for result in results): summary += " Higher-frequency FRED observations were converted to documented annual averages."
        if errors: summary += " The report uses all available datasets; unavailable sources are listed below."
        return jsonify({"success": True, "message": summary, "context_mode": context_mode, "context": {"countries": [c["name"] for c in context["countries"]], "metrics": [METRICS[m]["label"] for m in context["metrics"]], "start_year": context["start_year"], "end_year": context["end_year"]}, "sources": successes + failures, "preview": merged["rows"][:10], "columns": merged["columns"], "data": merged["rows"], "excel_available": True, "csv_available": True, "download_token": token})
    except ParseError as exc: return jsonify(friendly_error_payload(exc, message)), 400
    except Exception:
        app.logger.exception("Chat request failed"); return jsonify({"success": False, "error": "We couldn't build this report. Please try again."}), 500


def request_route():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict): raise ParseError('Input must be a JSON object.')
    message = payload.get('message', '')
    route = interpret_request(message, session.get('conversation'), session.get('web_context'))
    if payload.get('research_only') is True:
        route = {'structured': None, 'web': message, 'follow_up': False}
    return message, route


@app.post('/api/chat/plan')
def chat_plan():
    """Read-only preview so progress never falsely announces a web search."""
    try:
        _, route = request_route()
        steps = ['Understanding request...', 'Checking structured data sources...']
        if route['structured']:
            update = parse_request(route['structured'], require_complete=False)
            context = merge_context(session.get('conversation') if should_extend_context(route['structured'], session.get('conversation'), update) else None, update)
            names = sorted({task['source'] for task in build_plan(context)['tasks']})
            steps += [', '.join(names) + ' dataset found.', 'Fetching data...', 'Building report...']
        else:
            steps += ['No matching structured dataset found.']
        if route['web']:
            steps += ['Searching the web...', 'Ranking sources...', 'Preparing results...'] if WebSearchConnector().is_available() else ['Web search is not currently configured.']
        return jsonify({'steps': steps})
    except ParseError as exc:
        return jsonify(friendly_error_payload(exc)), 400


@app.post('/api/chat')
def chat():
    try:
        message, route = request_route()
        mode = 'mixed' if route['structured'] and route['web'] else 'structured' if route['structured'] else 'web'
        app.logger.info('request_mode=%s search_fallback=%s', mode, bool(route['web']))
        data, status = {}, 200
        if route['structured']:
            response = app.make_response(structured_chat(route['structured']))
            data, status = response.get_json(), response.status_code
        if not route['web']:
            session.pop('web_context', None)
            data['mode'] = mode
            return jsonify(data), status
        query, web_context = build_search_query(route['web'], session.get('web_context') if route['follow_up'] else None)
        # A mixed clause can inherit the explicitly requested country.
        if mode == 'mixed' and not web_context['country']:
            countries = parse_request(route['structured'], require_complete=False)['countries']
            if countries:
                web_context['country'] = countries[0]['name']
                query = (countries[0]['name'] + ' ' + query)[:500]
        session['web_context'] = web_context
        if mode == 'web': session.pop('conversation', None)
        connector = WebSearchConnector()
        research = {'query': query, 'results': [], 'provider': connector.provider,
                    'generated_at': datetime.now(timezone.utc).isoformat(), 'original_question': message}
        if not connector.is_available():
            research.update(status='not_configured', message="I couldn't find this in the connected structured datasets, and web search is not currently configured.")
        else:
            try:
                research.update(connector.search(query))
                research['status'] = 'success' if research['results'] else 'empty'
                research['message'] = 'I found relevant web sources for this question. Review the results below for the latest information.' if research['results'] else "I couldn't find a reliable source for this request. Try a more specific question."
                if research['results']:
                    excel, csv_file = generate_search_exports(message, research)
                    research['download_token'] = store_artifacts(excel, csv_file, {'mode': 'web'})
            except WebSearchError as exc:
                research.update(status='error', message=str(exc))
        app.logger.info('selected_connector=web_search provider=%s results=%d status=%s', connector.provider if connector.provider in {'tavily', 'tavily-keyless'} else 'unconfigured', len(research['results']), research['status'])
        data.update(mode=mode, web=research)
        if not data.get('success'):
            if data.get('error'): data['structured_error'] = data.pop('error')
            data.update(success=True, message=research['message'], excel_available=False, csv_available=False)
        return jsonify(data)
    except ParseError as exc:
        return jsonify(friendly_error_payload(exc)), 400
    except Exception:
        app.logger.error('Chat processing failed (details suppressed to protect credentials)')
        return jsonify({'success': False, 'error': "I couldn't complete this request right now. Please try again."}), 500

@app.get("/api/download/<token>/<file_type>")
def download_report(token, file_type):
    if file_type not in {"excel", "csv"}: return jsonify({"error": "Unsupported download type."}), 404
    with artifact_lock: artifact = artifacts.get(token)
    if not artifact or time.time() - artifact["created"] > ARTIFACT_TTL: return jsonify({"error": "This download has expired. Please run the query again."}), 404
    from io import BytesIO
    extension = "xlsx" if file_type == "excel" else "csv"; mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if file_type == "excel" else "text/csv"
    return send_file(BytesIO(artifact[file_type]), as_attachment=True, download_name=safe_report_name(artifact["context"], extension), mimetype=mimetype)

@app.post("/api/chat/reset")
def reset_chat():
    session.pop("conversation", None)
    session.pop('web_context', None)
    return jsonify({"success": True})

@app.errorhandler(413)
def too_large(_): return jsonify({"error": "Request is too large."}), 413

if __name__ == "__main__": app.run(debug=True)
