import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import sys
from .models import Job, TAIPEI
from .network import Http, Pages
from .report import send_document, write_reports
from .rules import classify
from .sources import Brave, collect
from .state import State


def publish(state, items, path, telegram=False):
    if telegram:
        send_document(path)
    state.acknowledge(items)


def run(config, demo=False, preview=False):
    now = datetime.now(TAIPEI)
    if demo:
        fixture = Path(__file__).resolve().parent.parent / 'demo' / 'fixtures.json'
        jobs = [Job(**item) for item in json.loads(fixture.read_text(encoding='utf-8'))]
        warnings = []
        stats = {'queries_ok': 0, 'candidates': len(jobs), 'pages_parsed': len(jobs)}
    else:
        key = os.environ.get('BRAVE_SEARCH_API_KEY', '').strip()
        if config.get('queries') and not key:
            raise ValueError('請先設定 BRAVE_SEARCH_API_KEY；離線試用請加 --demo')
        if not config.get('queries') and not config.get('seed_urls'):
            # Empty configuration must not silently look like a successful scan.
            raise ValueError('請設定 queries 或 seed_urls；搜尋需要 BRAVE_SEARCH_API_KEY')
        http = Http(timeout=config.get('timeout_seconds', 20), retries=2)
        jobs, warnings, stats = collect(config, Brave(http, key), Pages(http, config.get('page_interval_seconds', 1.2)))
        if not jobs and stats['candidates']:
            warnings.append('本次沒有取得可讀取的職缺資料，請檢查來源設定。')
    telegram = not demo and (config.get('telegram', False) or os.environ.get('TELEGRAM_ENABLED', '').lower() == 'true')
    if telegram and (not os.environ.get('TELEGRAM_BOT_TOKEN') or not os.environ.get('TELEGRAM_CHAT_ID')):
        raise ValueError('啟用 Telegram 需要 TELEGRAM_BOT_TOKEN 與 TELEGRAM_CHAT_ID')
    default_db = 'data/demo-state.db' if demo else 'data/state.db'
    state_path = config.get('state_path', default_db)
    if demo and state_path == 'data/state.db':
        state_path = 'data/demo-state.db'
    with State(state_path) as state:
        for job in jobs:
            state.observe(job, classify(job, now), now)
        pending = state.pending(now=now)
        path = write_reports(config.get('report_dir', 'reports'), pending, warnings, stats, now, demo)
        # Persist the complete report before acknowledging; failures leave outbox pending.
        if not preview:
            if pending:
                publish(state, pending, path, telegram)
            else:
                state.acknowledge(pending)
    result = {'pending': len(pending), 'warnings': len(warnings), 'report': str(path), 'demo': demo, 'preview': preview}
    print(json.dumps(result, ensure_ascii=False))
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as out:
            out.write(path.read_text(encoding='utf-8'))
    return result


def main():
    parser = argparse.ArgumentParser(description='台灣 Data Science 新鮮人職缺 bot')
    parser.add_argument('--config', default='config.json')
    parser.add_argument('--demo', action='store_true', help='不連網、不通知的合成資料示範')
    parser.add_argument('--preview', action='store_true', help='產生報告但保留待送狀態，不發送通知')
    args = parser.parse_args()
    try:
        config = json.loads(Path(args.config).read_text(encoding='utf-8-sig'))
        run(config, demo=args.demo, preview=args.preview)
        return 0
    except (RuntimeError, ValueError, OSError) as exc:
        print('執行失敗：' + str(exc), file=sys.stderr)
        return 1
