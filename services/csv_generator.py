import csv
from io import StringIO, BytesIO

def generate_csv(merged):
    text = StringIO(newline=""); writer = csv.DictWriter(text, fieldnames=merged["columns"]); writer.writeheader(); writer.writerows(merged["rows"])
    return BytesIO(text.getvalue().encode("utf-8-sig"))
