from services.source_router import SourceRouter
from concurrent.futures import ThreadPoolExecutor

def build_plan(context, router=None):
    router = router or SourceRouter()
    tasks = []
    for metric in context["metrics"]:
        source, _ = router.route(metric)
        if source == "worldbank":
            tasks.extend({"metric": metric, "source": source, "country": country, "start_year": context["start_year"], "end_year": context["end_year"]} for country in context["countries"])
        else:
            tasks.append({"metric": metric, "source": source, "start_year": context["start_year"], "end_year": context["end_year"]})
    return {"start_year": context["start_year"], "end_year": context["end_year"], "tasks": tasks}

def execute_plan(plan, router=None):
    router = router or SourceRouter(); results, errors = [], []
    def run_task(task):
        _, connector = router.route(task["metric"])
        try: return connector.fetch(task), None
        except Exception as exc: return None, {"source": connector.name, "metric": task["metric"], "country": task.get("country", {}).get("name"), "error": str(exc)}
    with ThreadPoolExecutor(max_workers=min(8, max(1, len(plan["tasks"])))) as executor:
        outcomes = executor.map(run_task, plan["tasks"])
        for result, error in outcomes:
            if result: results.append(result)
            if error: errors.append(error)
    return results, errors
