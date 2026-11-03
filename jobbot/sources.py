import time
from urllib.parse import urlencode
from .extract import extract_jobs
from .models import Job, canonical_url


class Brave:
    def __init__(self, http, key):
        self.http = http
        self.key = key
        self.last_request = 0

    def search(self, query, config):
        results = []
        for offset in range(min(10, max(1, config.get('pages_per_query', 1)))):
            time.sleep(max(0, config.get('search_interval_seconds', 1.1) - (time.monotonic() - self.last_request)))
            params = {'q': query, 'country': 'tw', 'count': min(20, max(1, config.get('results_per_query', 20))), 'offset': offset}
            if config.get('freshness'):
                params['freshness'] = config['freshness']
            try:
                payload = self.http.json('https://api.search.brave.com/res/v1/web/search?' + urlencode(params),
                                         {'X-Subscription-Token': self.key, 'Accept': 'application/json'})
            finally:
                self.last_request = time.monotonic()
            if not isinstance(payload, dict) or 'error' in payload or not isinstance(payload.get('web', {}), dict):
                raise RuntimeError('搜尋 API 回應格式錯誤')
            results.extend(payload.get('web', {}).get('results', []))
            if not payload.get('query', {}).get('more_results_available'):
                break
        return results


def collect(config, search, pages):
    warnings = []
    candidates = {}
    ok = 0
    for query in config.get('queries', []):
        try:
            found = search.search(query, config)
            ok += 1
            for item in found:
                url = item.get('url', '')
                if url.startswith(('https://', 'http://')):
                    candidates.setdefault(canonical_url(url), item)
        except RuntimeError as exc:
            warnings.append('搜尋部分失敗：%s（%s）' % (query, exc))
    if config.get('queries') and ok == 0:
        raise RuntimeError('全部搜尋失敗；未將本次結果當成零職缺。' + '；'.join(warnings))
    # Explicit seeds are useful for known employer/ATS postings outside the index.
    for url in config.get('seed_urls', []):
        candidates.setdefault(canonical_url(url), {'url': url, 'title': 'Data Scientist（手動來源，待解析）'})
    limit = max(1, int(config.get('max_pages', 100)))
    if len(candidates) > limit:
        warnings.append('找到 %s 個網址，本次頁面上限 %s；請提高 max_pages 以涵蓋其餘候選。' % (len(candidates), limit))
    jobs = []
    fetched = 0
    for url, item in list(candidates.items())[:limit]:
        try:
            page = pages.fetch(url)
            extracted = extract_jobs(page, url)
            if not extracted:
                raise RuntimeError('沒有可核實的 JobPosting JSON-LD（可能需要 JavaScript/登入或不是單一職缺頁）')
            jobs.extend(extracted)
            fetched += 1
        except (RuntimeError, ValueError, TypeError) as exc:
            warnings.append('%s：%s' % (url, exc))
            jobs.append(Job(title=item.get('title', ''), company='', location='',
                            description=item.get('description', ''), url=url, verified=False))
    return jobs, warnings, {'queries_ok': ok, 'candidates': len(candidates), 'pages_parsed': fetched}
