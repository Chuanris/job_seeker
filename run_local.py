"""Local deployment launcher: stable working directory and private .env loading."""
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Anaconda on Windows needs its own SQLite DLL before importing sqlite3.
_dll_handle = None
_library_bin = Path(sys.prefix) / 'Library' / 'bin'
if os.name == 'nt' and _library_bin.is_dir():
    os.environ['PATH'] = str(_library_bin) + os.pathsep + os.environ.get('PATH', '')
    if hasattr(os, 'add_dll_directory'):
        _dll_handle = os.add_dll_directory(str(_library_bin))

_env_file = ROOT / '.env'
if _env_file.exists():
    for _line in _env_file.read_text(encoding='utf-8-sig').splitlines():
        _line = _line.strip()
        if not _line or _line.startswith('#'):
            continue
        _key, _sep, _value = _line.partition('=')
        _key = _key.strip()
        if _sep and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', _key):
            _value = _value.strip()
            if len(_value) >= 2 and _value[0] == _value[-1] and _value[0] in ('"', "'"):
                _value = _value[1:-1]
            if _value:
                os.environ.setdefault(_key, _value)

from jobbot.cli import main

if __name__ == '__main__':
    # Scheduled tasks have no terminal. Keep their output in a private local log.
    if '--scheduled' in sys.argv:
        from datetime import datetime
        from jobbot.models import TAIPEI
        sys.argv.remove('--scheduled')
        _log_dir = ROOT / 'logs'
        _log_dir.mkdir(exist_ok=True)
        with (_log_dir / 'daily.log').open('a', encoding='utf-8', buffering=1) as _log:
            sys.stdout = sys.stderr = _log
            print('\nRun at ' + datetime.now(TAIPEI).isoformat())
            raise SystemExit(main())
    raise SystemExit(main())
