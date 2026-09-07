"""Deterministic search construction and small, replaceable conversation context."""
import re
from services.parser import COUNTRIES


def build_search_query(question, previous=None):
    text = question.replace('’', "'").strip()
    follow_up = bool(previous and re.match(r'^(what about|how about|and|also)\b', text, re.I))
    country = ''
    for name, _, aliases in COUNTRIES:
        if any(re.search(r'\b' + re.escape(alias) + r'\b', text, re.I) for alias in aliases):
            country = 'UAE' if name == 'United Arab Emirates' else name
            break
    if follow_up:
        topic = previous['topic']
        country = country or previous.get('country', '')
    else:
        topic = re.sub(r"'s\b", '', text)
        for name, _, aliases in COUNTRIES:
            for alias in sorted(aliases + [name], key=len, reverse=True):
                topic = re.sub(r'\b' + re.escape(alias) + r'\b', '', topic, flags=re.I)
        topic = re.sub(r'^(?:please\s+)?(?:what is|what are|how much|find|show|tell me about|explain)\s*', '', topic, flags=re.I)
        topic = re.sub(r'\b(?:the latest information about|information about|tell me about)\b', '', topic, flags=re.I)
        topic = re.sub(r'\b(?:expected to reach by)\b', 'size forecast', topic, flags=re.I)
        if re.search('renewable energy', topic, re.I):
            topic = re.sub(r'\b(?:does|produce)\b', '', topic, flags=re.I) + ' production statistics'
        topic = re.sub(r'[?!.]', '', topic)
        topic = ' '.join(topic.split()).strip()
    query = ' '.join((country + ' ' + topic).split())
    if not re.search(r'\b(?:19\d{2}|20\d{2}|latest)\b', query, re.I):
        query += ' latest'
    return query[:500], {'topic': topic[:350], 'country': country, 'mode': 'web'}
