def series_label(result): return f'{result["country"]} {result["metric"]}' if result.get("country") else result["metric"]

def merge_results(results, start_year, end_year):
    columns = [series_label(result) for result in results]
    lookups = [{row["period"]: row["value"] for row in result["records"]} for result in results]
    rows = [{"Year": year, **{column: lookup.get(year) for column, lookup in zip(columns, lookups)}} for year in range(start_year, end_year + 1)]
    return {"columns": ["Year"] + columns, "rows": rows}
