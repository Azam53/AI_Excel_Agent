"""Route informational clauses independently; keep the existing metric parser intact."""
import re
from services.parser import COUNTRIES, ParseError, parse_request, should_extend_context


def split_mixed_clause(clause):
    for match in re.finditer(r'\band\b', clause, re.I):
        left, right = clause[:match.start()], clause[match.end():]
        try:
            first = parse_request(left, require_complete=False)
            second = parse_request(right, require_complete=False)
        except ParseError:
            continue
        if not first['metrics'] or second['metrics']:
            continue
        remainder = right.lower()
        for name, _, aliases in COUNTRIES:
            for alias in aliases + [name.lower()]:
                remainder = re.sub(r'\b' + re.escape(alias) + r"(?:'s)?\b", '', remainder)
        words = set(re.findall(r'[a-z]+', remainder)) - {'from', 'to', 'in', 'the', 'last', 'years', 'year', 'chart', 'charts', 'with', 'a', 'csv', 'excel', 'report', 'show', 'data', 'for', 's'}
        if len(words) >= 2:
            return left, right
    return None


def interpret_request(message, previous=None, web_context=None):
    if not isinstance(message, str) or not message.strip():
        raise ParseError('Please enter a data request.')
    if len(message) > 500:
        raise ParseError('Please keep your request under 500 characters.')
    if re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', message) or not re.search(r'[a-zA-Z]{2}', message):
        raise ParseError('Please enter an interpretable information question.')
    if re.fullmatch(r'\s*tell me something about \w+\s*[?.]?\s*', message, re.I):
        raise ParseError('I need a measurable topic before I can build the report.')
    if web_context and re.match(r'^\s*(what about|how about|and|also)\b', message, re.I):
        return {'structured': None, 'web': message, 'follow_up': True}
    # Do not split countries, metric lists, or "between 2015 and 2025".
    clauses = re.split(r'\s*(?:;|\band\s+(?=(?:find|tell|what|why|explain|search|how)\b))\s*', message, flags=re.I)
    structured, research = [], []
    for clause in clauses:
        mixed = split_mixed_clause(clause)
        if mixed:
            structured.append(mixed[0])
            research.append(mixed[1])
            continue
        if re.search(r'\b(?:expected to reach|outlook|news|latest information|market size)\b', clause, re.I):
            # A familiar metric word in a research question does not make it observations.
            research.append(clause)
            continue
        try:
            parsed = parse_request(clause, require_complete=False)
        except ParseError as exc:
            if exc.code not in {'forecast', 'explanation'}:
                raise
            research.append(clause)
            continue
        if parsed['metrics'] or should_extend_context(clause, previous, parsed):
            structured.append(clause)
        else:
            research.append(clause)
    return {'structured': ' and '.join(structured) or None,
            'web': ' '.join(research) or None, 'follow_up': False}
