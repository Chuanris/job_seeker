from datetime import datetime
import json
from pathlib import Path
from .models import TAIPEI


def cell(value):
    return str(value or '未公開/未註明').replace('|', '\\|').replace('\n', ' ').replace('\r', ' ')


def write_reports(directory, items, warnings, stats, now, demo=False):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    name = now.astimezone(TAIPEI).strftime('%Y%m%d-%H%M%S-%f')
    prefix = 'demo-' if demo else ''
    path = directory / (prefix + name + '.md')
    lines = ['# 台灣 Data Science 新鮮人職缺', '', '查核時間：' + now.astimezone(TAIPEI).isoformat(), '']
    if demo:
        lines += ['**合成示範資料：以下公司與職缺為測試用途，不是真實招募資訊。**', '']
    lines += ['新增或有實質變動 %s 筆。搜尋成功 %s 組；發現 %s 個候選網址；解析 %s 個頁面。' %
              (len(items), stats.get('queries_ok', 0), stats.get('candidates', 0), stats.get('pages_parsed', 0)), '']
    for status, heading in [('confirmed', '已核實零年經驗資格'), ('review', '資格待確認')]:
        group = [x for x in items if x['decision']['status'] == status]
        if not group:
            continue
        lines += ['## ' + heading, '', '| 公司／職稱 | 地點／型態 | 薪資 | 資格依據／待確認 | 日期 | 來源 |', '|---|---|---|---|---|---|']
        for item in group:
            job = item['job']
            links = ' / '.join('[來源 %s](%s)' % (i + 1, u.replace(')', '%29')) for i, u in enumerate(item['urls']))
            lines.append('| %s | %s | %s | %s | %s | %s |' % (
                cell(('更新：' if item['is_update'] else '新增：') + (job['company'] or '雇主未核實') + ' / ' + job['title']),
                cell(job['location'] + ' / ' + job['employment']), cell(job['salary']), cell(item['decision']['reason']),
                cell('刊登：' + (job['posted'] or '未註明') + '；首次發現：' + item['first_seen'][:10]), links))
        lines.append('')
        for item in group:
            job = item['job']
            lines += ['- **%s**：學歷：%s；內文節錄：%s' % (cell(job['title']), cell(job['education']), cell(job['description'][:500])), '']
    if warnings:
        lines += ['## 來源與執行限制', ''] + ['- ' + x for x in warnings] + ['']
    lines += ['依公開頁面規則篩選；未見關閉標示不代表雇主保證仍有名額。投遞前請複查資格、地點與截止日。', '']
    path.write_text('\n'.join(lines), encoding='utf-8')
    payload = {'checked_at': now.isoformat(), 'demo': demo, 'items': items, 'warnings': warnings, 'stats': stats}
    path.with_suffix('.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    return path


def send_document(path):
    # One document avoids Telegram message-length truncation and partial batches.
    import os
    import uuid
    from .network import Http
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    chat = os.environ.get('TELEGRAM_CHAT_ID', '')
    if not token or not chat:
        raise ValueError('啟用 Telegram 需要 TELEGRAM_BOT_TOKEN 與 TELEGRAM_CHAT_ID')
    boundary = 'jobbot-' + uuid.uuid4().hex
    parts = [('--' + boundary + '\r\nContent-Disposition: form-data; name="chat_id"\r\n\r\n' + chat + '\r\n').encode(),
             ('--' + boundary + '\r\nContent-Disposition: form-data; name="document"; filename="jobs.md"\r\nContent-Type: text/markdown; charset=utf-8\r\n\r\n').encode(),
             Path(path).read_bytes(), ('\r\n--' + boundary + '--\r\n').encode()]
    result = Http(retries=0).json('https://api.telegram.org/bot' + token + '/sendDocument',
                                 {'Content-Type': 'multipart/form-data; boundary=' + boundary}, b''.join(parts))
    if not result.get('ok'):
        raise RuntimeError('Telegram 未確認收件；待送項目保留於資料庫')
