def normalize_result(result):
    normalized = dict(result)
    normalized["records"] = [{"period": int(row["period"]), "value": (float(row["value"]) if row.get("value") is not None else None)} for row in result.get("records", [])]
    return normalized
