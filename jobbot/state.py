"""SQLite outbox: discovering a vacancy is separate from acknowledging delivery."""
from dataclasses import asdict
import json
import sqlite3
from pathlib import Path
from .models import Job, canonical_url
from .rules import classify


class State:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute('''CREATE TABLE IF NOT EXISTS jobs (
            key TEXT PRIMARY KEY, payload TEXT NOT NULL, decision TEXT NOT NULL,
            fingerprint TEXT NOT NULL, delivered TEXT, first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL, urls TEXT NOT NULL)''')
        self.db.execute('CREATE TABLE IF NOT EXISTS aliases (url TEXT PRIMARY KEY, job_key TEXT NOT NULL)')
        for row in self.db.execute('SELECT key, urls FROM jobs').fetchall():
            self.db.executemany('INSERT OR IGNORE INTO aliases VALUES(?,?)',
                                [(canonical_url(url), row['key']) for url in json.loads(row['urls'])])
        self.db.commit()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.db.close()

    def observe(self, job, decision, now):
        key = job.key()
        alias = self.db.execute('SELECT job_key FROM aliases WHERE url=?', (canonical_url(job.url),)).fetchone()
        if alias:
            key = alias['job_key']
        old = self.db.execute('SELECT * FROM jobs WHERE key=?', (key,)).fetchone()
        # A fetch failure must not overwrite a previously verified vacancy.
        if old and not job.verified and json.loads(old['payload'])['verified']:
            return
        urls = set(json.loads(old['urls'])) if old else set()
        urls.add(job.url)
        self.db.execute('''INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?)
            ON CONFLICT(key) DO UPDATE SET payload=excluded.payload,
            decision=excluded.decision, fingerprint=excluded.fingerprint,
            last_seen=excluded.last_seen, urls=excluded.urls''',
            (key, json.dumps(asdict(job), ensure_ascii=False), json.dumps(asdict(decision), ensure_ascii=False),
             job.fingerprint(decision.status), old['delivered'] if old else None,
             old['first_seen'] if old else now.isoformat(), now.isoformat(), json.dumps(sorted(urls))))
        self.db.execute('INSERT OR REPLACE INTO aliases VALUES(?,?)', (canonical_url(job.url), key))
        self.db.commit()

    def pending(self, now=None):
        out = []
        rows = self.db.execute('SELECT * FROM jobs WHERE delivered IS NULL OR delivered != fingerprint ORDER BY first_seen, key').fetchall()
        for row in rows:
            item = dict(row)
            item['job'] = json.loads(item.pop('payload'))
            item['decision'] = json.loads(item['decision'])
            if now is not None:
                job = Job(**item['job'])
                decision = classify(job, now)
                item['decision'] = asdict(decision)
                item['fingerprint'] = job.fingerprint(decision.status)
                self.db.execute('UPDATE jobs SET decision=?, fingerprint=? WHERE key=?',
                                (json.dumps(item['decision'], ensure_ascii=False), item['fingerprint'], item['key']))
            item['urls'] = json.loads(item['urls'])
            item['is_update'] = item['delivered'] is not None
            if item['decision']['status'] != 'excluded':
                out.append(item)
        self.db.commit()
        return sorted(out, key=lambda x: (x['decision']['status'] != 'confirmed', x['first_seen']))

    def acknowledge(self, items):
        self.db.executemany('UPDATE jobs SET delivered=? WHERE key=? AND fingerprint=?',
                            [(x['fingerprint'], x['key'], x['fingerprint']) for x in items])
        self.db.commit()
