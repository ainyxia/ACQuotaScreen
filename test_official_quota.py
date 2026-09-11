import json, tempfile, unittest
from datetime import datetime, timezone
from pathlib import Path
from official_quota import OfficialQuota

class OfficialQuotaTests(unittest.TestCase):
    def test_reads_latest_and_expires(self):
        with tempfile.TemporaryDirectory() as root:
            now=1789140000; folder=Path(root)/'sessions'/datetime.fromtimestamp(now).strftime('%Y/%m/%d'); folder.mkdir(parents=True)
            def rec(ts, used): return json.dumps({'timestamp':datetime.fromtimestamp(ts,timezone.utc).isoformat(),'type':'event_msg','payload':{'type':'token_count','rate_limits':{'primary':{'used_percent':used,'window_minutes':10080,'resets_at':now+60},'credits':{},'plan_type':'pro'}}})
            (folder/'test.jsonl').write_text(rec(now-20,25)+'\n'+rec(now-10,30)+'\n',encoding='utf-8')
            q=OfficialQuota(root); self.assertEqual(q.sample(now)['remaining'],70); self.assertEqual(q.sample(now+61)['status'],'waiting_refresh')
    def test_missing(self):
        with tempfile.TemporaryDirectory() as root: self.assertIsNone(OfficialQuota(root).sample(1789140000))

if __name__=='__main__': unittest.main()
