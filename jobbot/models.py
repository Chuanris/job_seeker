from dataclasses import asdict, dataclass
from datetime import timedelta, timezone
import hashlib
import json
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TAIPEI = timezone(timedelta(hours=8), 'Asia/Taipei')


def canonical_url(url):
    parts = urlsplit(url)
    ignored = {'ref', 'src', 'source', 'jobsource', 'trk', 'trackingid', 'urlhash'}
    query = [(k, v) for k, v in parse_qsl(parts.query) if not k.lower().startswith('utm_') and k.lower() not in ignored]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip('/'), urlencode(sorted(query)), ''))


def normalize(value):
    return re.sub(r'[\W_]+', '', value.casefold())


@dataclass
class Job:
    title: str
    company: str
    location: str
    description: str
    url: str
    employment: str = ''
    salary: str = ''
    education: str = ''
    posted: str = ''
    expires: str = ''
    identifier: str = ''
    min_months: object = None
    verified: bool = False
    closed: bool = False

    def key(self):
        # Explicit employer identity allows cross-board merging. Unknown employers
        # remain URL-specific to avoid conflating unrelated search snippets.
        identity = '|'.join(normalize(x) for x in (self.company, self.title, self.location))
        if not self.company or not self.location:
            identity = canonical_url(self.url)
        return hashlib.sha256(identity.encode('utf-8')).hexdigest()

    def fingerprint(self, status):
        fields = asdict(self)
        for key in ('url', 'posted', 'identifier'):
            fields.pop(key)
        fields['status'] = status
        return hashlib.sha256(json.dumps(fields, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


@dataclass
class Decision:
    status: str
    reason: str
