"""Optional search API adapter. Never fetch result URLs or synthesize answers."""
import ipaddress
import logging
import os
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit

import requests

logger = logging.getLogger(__name__)


class WebSearchError(RuntimeError):
    pass


def safe_url(value):
    if not isinstance(value, str) or len(value) > 2048 or re.search(r'[\s\\\x00-\x1f\x7f]', value):
        return False
    try:
        url = urlsplit(value)
        host = url.hostname
        if url.scheme not in {'http', 'https'} or not host or url.username or url.password:
            return False
        if not url.port in (None, 80, 443) or '.' not in host or host.endswith(('.local', '.localhost')):
            return False
        try:
            return ipaddress.ip_address(host).is_global
        except ValueError:
            return bool(re.fullmatch(r'[a-zA-Z0-9.-]+', host))
    except ValueError:
        return False


def source_authority(domain):
    if domain.endswith(('.gov', '.gov.in', '.gov.uk', '.gov.ae', '.gc.ca', '.gov.au')):
        return 1.0, 'Government website'
    if domain.endswith(('.edu', '.ac.uk', '.ac.in')):
        return .8, 'University'
    trusted = ('worldbank.org', 'imf.org', 'oecd.org', 'un.org', 'who.int', 'ilo.org',
               'iea.org', 'irena.org', 'federalreserve.gov', 'stlouisfed.org', 'nber.org')
    if any(domain == host or domain.endswith('.' + host) for host in trusted):
        return 1.0, 'Research / economic institution'
    return 0.0, 'Web source'


def normalize_results(query, items, max_results=5):
    tokens = set(re.findall(r'\w+', query.lower())) - {'latest', 'the', 'and', 'of'}
    ranked, seen = [], set()
    for item in items[:10]:
        if not isinstance(item, dict) or not safe_url(item.get('url')):
            continue
        url = item['url']
        if url in seen:
            continue
        seen.add(url)
        domain = urlsplit(url).hostname.lower().removeprefix('www.')
        title = str(item.get('title') or domain)[:300]
        snippet = str(item.get('content') or item.get('snippet') or '')[:2000]
        authority, category = source_authority(domain)
        published, recency = None, 0
        try:
            stamp = datetime.fromisoformat(str(item.get('published_date', '')).replace('Z', '+00:00'))
            age = (datetime.now(timezone.utc) - stamp.replace(tzinfo=stamp.tzinfo or timezone.utc)).days
            if age >= 0:
                published = stamp.date().isoformat()
                recency = max(0, 1 - age / 730)
        except ValueError:
            pass
        words = set(re.findall(r'\w+', (title + ' ' + snippet).lower()))
        relevance = len(tokens & words) / max(1, len(tokens))
        ranked.append((relevance * 3 + authority + recency * .3, {
            'title': title, 'url': url, 'snippet': snippet, 'domain': domain,
            'source': domain, 'published_date': published, 'category': category,
        }))
    ranked.sort(key=lambda entry: entry[0], reverse=True)
    return [item for _, item in ranked[:max(1, min(10, max_results))]]


class WebSearchConnector:
    name = 'Web Search'

    def __init__(self, provider=None, api_key=None, session=None):
        self.provider = (provider if provider is not None else os.getenv('WEB_SEARCH_PROVIDER', '')).strip().lower()
        self.api_key = api_key if api_key is not None else os.getenv('WEB_SEARCH_API_KEY', '')
        self.session = session or requests

    def is_available(self):
        return self.provider == 'tavily-keyless' or (self.provider == 'tavily' and bool(self.api_key.strip()))

    def status(self):
        available = self.is_available()
        return {'name': self.name, 'type': 'search', 'available': available,
                'status': 'connected' if available else 'not_configured',
                'message': ('Keyless demo — rate limited' if self.provider == 'tavily-keyless' else 'Configured (not a live health check)') if available else 'Optional — configure Tavily keyless mode or API key'}

    def search(self, query, max_results=5):
        if not isinstance(query, str) or not query.strip() or len(query) > 500:
            raise WebSearchError('Search query must contain 1–500 characters.')
        if not self.is_available():
            raise WebSearchError('Web search is not currently configured.')
        try:
            response = self.session.post('https://api.tavily.com/search',
                headers=({'X-Tavily-Access-Mode': 'keyless'} if self.provider == 'tavily-keyless' else {'Authorization': 'Bearer ' + self.api_key}),
                json={'query': query, 'max_results': 10, 'search_depth': 'basic',
                      'include_answer': False, 'include_raw_content': False},
                timeout=(5, 25), allow_redirects=False)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get('results'), list):
                raise ValueError('Invalid search response')
            results = normalize_results(query, payload['results'], max_results)
        except (requests.RequestException, ValueError, TypeError):
            logger.warning('Search provider failed provider=tavily')
            raise WebSearchError("I couldn't complete the web search right now. Please try again.") from None
        logger.info('selected_connector=web_search provider=tavily results=%d', len(results))
        return {'query': query, 'results': results, 'provider': self.provider}
