"""Bounded HTTP requests, explicit errors and public-page robots policy."""
import json
import time
from urllib import error, request
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

USER_AGENT = 'TaiwanDSJobBot/1.0'


class Http:
    def __init__(self, timeout=20, retries=2):
        self.timeout = timeout
        self.retries = retries

    def get(self, url, headers=None, data=None):
        if urlsplit(url).scheme not in ('https', 'http'):
            raise ValueError('僅接受 http/https URL')
        for attempt in range(self.retries + 1):
            try:
                req = request.Request(url, data=data, headers={'User-Agent': USER_AGENT, **(headers or {})})
                with request.urlopen(req, timeout=self.timeout) as response:
                    raw = response.read(3_000_001)
                    if len(raw) > 3_000_000:
                        raise RuntimeError('頁面超過 3 MB 限制')
                    charset = response.headers.get_content_charset() or 'utf-8'
                    return raw.decode(charset, errors='replace')
            except error.HTTPError as exc:
                if (exc.code == 429 or 500 <= exc.code < 600) and attempt < self.retries and data is None:
                    retry_after = exc.headers.get('Retry-After', '')
                    delay = min(30, int(retry_after)) if retry_after.isdigit() else 2 ** attempt
                    time.sleep(delay)
                    continue
                # Do not expose URLs: Telegram puts the bot token in the URL.
                raise RuntimeError('HTTP %s' % exc.code) from None
            except (error.URLError, TimeoutError, OSError):
                if attempt < self.retries and data is None:
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError('連線失敗或逾時') from None

    def json(self, url, headers=None, data=None):
        try:
            return json.loads(self.get(url, headers, data))
        except (ValueError, TypeError):
            raise RuntimeError('伺服器未回傳有效 JSON') from None


class Pages:
    def __init__(self, http, delay=1.2):
        self.http = http
        self.delay = delay
        self.robots = {}
        self.last_request = {}

    def fetch(self, url):
        parsed = urlsplit(url)
        origin = '%s://%s' % (parsed.scheme, parsed.netloc)
        if origin not in self.robots:
            robot = RobotFileParser()
            try:
                robot.parse(self.http.get(origin + '/robots.txt').splitlines())
            except RuntimeError as exc:
                if str(exc) == 'HTTP 404':
                    robot.parse(['User-agent: *', 'Allow: /'])
                else:
                    raise RuntimeError('無法核實 robots.txt（%s）' % exc) from None
            self.robots[origin] = robot
            self.last_request[origin] = time.monotonic()
        robot = self.robots[origin]
        if not robot.can_fetch(USER_AGENT, url):
            raise RuntimeError('robots.txt 不允許讀取')
        delay = max(self.delay, robot.crawl_delay(USER_AGENT) or 0)
        time.sleep(max(0, delay - (time.monotonic() - self.last_request.get(origin, 0))))
        try:
            return self.http.get(url)
        finally:
            self.last_request[origin] = time.monotonic()
