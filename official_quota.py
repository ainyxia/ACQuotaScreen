"""Read official Codex quota snapshots from local session event JSONL files."""
import json
import os
import time
from datetime import datetime
from pathlib import Path


class OfficialQuota:
    def __init__(self, root=None):
        self.root = Path(root or os.environ.get("CODEX_OFFICIAL_HOME", Path.home()/".codex-official")) / "sessions"
        self.snapshot = None
        self.source_file = None
        self.scanned = 0

    def _paths(self, now):
        paths = []
        for day in range(14):
            date = datetime.fromtimestamp(now-day*86400)
            paths.extend((self.root/date.strftime('%Y')/date.strftime('%m')/date.strftime('%d')).glob('*.jsonl'))
        return sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True)[:40]

    def sample(self, now=None):
        now = time.time() if now is None else now
        if now - self.scanned > 10 or self.source_file is None:
            paths = self._paths(now)
            self.scanned = now
        else:
            paths = [self.source_file]
        latest = None
        latest_ts = 0
        latest_path = None
        for path in paths:
            try:
                with path.open('r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            rec = json.loads(line)
                            payload = rec.get('payload', {})
                            if rec.get('type') != 'event_msg' or payload.get('type') != 'token_count':
                                continue
                            limits = payload.get('rate_limits')
                            if not isinstance(limits, dict) or not limits.get('primary'):
                                continue
                            ts = rec.get('timestamp', '')
                            try: stamp = datetime.fromisoformat(ts.replace('Z', '+00:00')).timestamp()
                            except Exception: stamp = path.stat().st_mtime
                            if stamp >= latest_ts:
                                latest, latest_ts, latest_path = (payload, stamp, path)
                        except (ValueError, TypeError, OSError):
                            continue
            except (OSError, UnicodeError):
                continue
        if latest is not None:
            self.snapshot, self.source_file = latest, latest_path
        snap = self.snapshot
        if not snap:
            return None
        limits = snap.get('rate_limits') or {}
        primary = limits.get('primary') or {}
        reset = primary.get('resets_at')
        if isinstance(reset, (int, float)) and now >= reset:
            return dict(status='waiting_refresh', plan='官方 Codex', unit='%', remaining=None, windows=[], resets_at=reset)
        used = primary.get('used_percent')
        if not isinstance(used, (int, float)):
            return None
        windows = [dict(name='官方主窗口', limit=100, used=used, remaining=max(0, 100-used), resets_at=reset,
                        window_minutes=primary.get('window_minutes'))]
        secondary = limits.get('secondary')
        if isinstance(secondary, dict) and isinstance(secondary.get('used_percent'), (int, float)):
            su = secondary['used_percent']
            windows.append(dict(name='官方次窗口', limit=100, used=su, remaining=max(0, 100-su), resets_at=secondary.get('resets_at'), window_minutes=secondary.get('window_minutes')))
        credits = limits.get('credits') or {}
        plan = '官方 Codex' + ((' · ' + str(limits.get('plan_type'))) if limits.get('plan_type') else '')
        return dict(remaining=max(0, 100-used), plan=plan, unit='%', windows=windows,
                    expires=None, today=None, usage={}, valid=True, status='active', resets_at=reset,
                    credits=credits)
