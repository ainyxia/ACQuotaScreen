"""Read-only, bounded local session-event watcher. Never exports conversation content."""
import json
import os
import time
from datetime import datetime
from pathlib import Path

LABELS = {'working': '工作中', 'waiting': '等待确认', 'complete': '已完成',
          'error': '任务出错', 'idle': '待机', 'unknown': '状态未知'}
WAIT_TOOLS = {'request_user_input', 'request_permissions'}


def classify(record):
    payload = record.get('payload', {})
    if not isinstance(payload, dict):
        return None
    kind = payload.get('type')
    if record.get('type') == 'event_msg':
        if kind in ('task_started', 'turn_started'):
            return 'working'
        if kind in ('task_complete', 'turn_completed'):
            return 'complete'
        if kind in ('turn_aborted', 'task_cancelled'):
            return 'idle'
        if kind in ('error', 'task_failed', 'turn_failed'):
            return 'error'
        if kind in ('exec_approval_request', 'apply_patch_approval_request', 'request_user_input'):
            return 'waiting'
    if record.get('type') == 'response_item':
        if kind == 'function_call':
            name = str(payload.get('name', '')).split('.')[-1]
            return 'waiting' if name in WAIT_TOOLS else 'working'
        if kind in ('function_call_output', 'reasoning', 'web_search_call'):
            return 'working'
        if kind == 'message' and payload.get('role') == 'assistant':
            return 'complete' if payload.get('phase') == 'final' else 'working'
    return None


class SessionTail:
    def __init__(self, path):
        self.path = path
        self.offset = 0
        self.initial = True
        self.status = 'unknown'
        self.updated = 0

    def read(self):
        size = self.path.stat().st_size
        if size < self.offset:
            self.offset = 0
            self.initial = True
            self.status, self.updated = 'unknown', 0
        with self.path.open('rb') as stream:
            start = max(self.offset, size-524288)
            stream.seek(start)
            if start > self.offset or self.initial and start:
                stream.readline()  # Discard an incomplete first record.
            self.initial = False
            while True:
                pos = stream.tell()
                line = stream.readline(524289)
                if not line:
                    self.offset = pos
                    break
                if not line.endswith(b'\n'):
                    self.offset = pos
                    break
                self.offset = stream.tell()
                try:
                    record = json.loads(line)
                    status = classify(record)
                    if status:
                        timestamp = datetime.fromisoformat(record['timestamp'].replace('Z', '+00:00')).timestamp()
                        if timestamp >= self.updated:
                            self.status, self.updated = status, timestamp
                except (ValueError, KeyError, TypeError, AttributeError):
                    continue


class CodexStatus:
    def __init__(self, root=None):
        self.root = Path(root or os.environ.get('CODEX_HOME', Path.home()/'.codex'))/'sessions'
        self.tails = {}
        self.scanned = 0

    def sample(self, now=None):
        now = time.time() if now is None else now
        try:
            if now-self.scanned > 15:
                # Date directories avoid walking historical session contents.
                paths = []
                for day in range(3):
                    date = datetime.fromtimestamp(now-day*86400)
                    folder = self.root/date.strftime('%Y')/date.strftime('%m')/date.strftime('%d')
                    paths.extend(folder.glob('*.jsonl'))
                paths = sorted(paths, key=lambda p:p.stat().st_mtime, reverse=True)[:16]
                self.tails = {p:self.tails.get(p, SessionTail(p)) for p in paths}
                self.scanned = now
            for tail in self.tails.values():
                tail.read()
        except OSError:
            return self.result('unknown', 0, 0)
        fresh = [t for t in self.tails.values() if 0 <= now-t.updated < 600]
        active = [t for t in fresh if t.status in ('working', 'waiting')]
        if active:
            chosen = max(active, key=lambda t:(t.status == 'waiting', t.updated))
        else:
            chosen = max(fresh, key=lambda t:t.updated, default=None)
        if chosen is None:
            return self.result('unknown' if not self.tails else 'idle', 0, 0)
        status = chosen.status
        if status in ('complete', 'error') and now-chosen.updated > 45:
            status = 'idle'
        return self.result(status, chosen.updated, len(active))

    @staticmethod
    def result(status, updated, active):
        return dict(status=status, label=LABELS[status], updated=updated,
                    active_tasks=active, source='local_session_events')
