import json
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

from codex_status import classify, CodexStatus, SessionTail


class StatusTests(unittest.TestCase):
    def test_event_types(self):
        for kind, state in [('task_started','working'), ('task_complete','complete'),
                            ('turn_aborted','idle'), ('task_failed','error'),
                            ('exec_approval_request','waiting')]:
            self.assertEqual(classify(dict(type='event_msg', payload=dict(type=kind))), state)
        self.assertIsNone(classify(dict(type='event_msg', payload=dict(type='token_count'))))
        self.assertEqual(classify(dict(type='response_item', payload=dict(type='function_call', name='functions.request_user_input'))), 'waiting')
        self.assertEqual(classify(dict(type='response_item', payload=dict(type='function_call_output', output='test error text'))), 'working')

    def test_partial_tail_and_expiry(self):
        with tempfile.TemporaryDirectory() as root:
            now=time.time()
            folder=Path(root)/'sessions'/datetime.fromtimestamp(now).strftime('%Y/%m/%d')
            folder.mkdir(parents=True)
            path=folder/'test.jsonl'
            def event(kind):
                return json.dumps(dict(timestamp=datetime.fromtimestamp(now,timezone.utc).isoformat(),type='event_msg',payload=dict(type=kind)))
            path.write_text(event('task_started')+'\n',encoding='utf-8')
            watcher=CodexStatus(root)
            self.assertEqual(watcher.sample(now)['status'],'working')
            complete=event('task_complete')
            with path.open('a',encoding='utf-8') as f:f.write(complete[:20])
            self.assertEqual(watcher.sample(now+1)['status'],'working')
            with path.open('a',encoding='utf-8') as f:f.write(complete[20:]+'\n')
            result=watcher.sample(now+2)
            self.assertEqual(result['status'],'complete')
            self.assertNotIn('payload',result)
            self.assertEqual(watcher.sample(now+60)['status'],'idle')
            path.write_text(event('task_started')+'\n',encoding='utf-8')
            self.assertEqual(watcher.sample(now+700)['status'],'idle')


if __name__ == '__main__':
    unittest.main()
