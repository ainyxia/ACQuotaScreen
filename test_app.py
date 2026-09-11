import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import config_store as store
from service import parse_ccs, ccs_link, endpoint_url, summary


class Tests(unittest.TestCase):
    def test_touch_release_keeps_position(self):
        from touch_input import TouchTracker, position, coalesce
        tracker = TouchTracker()
        report = bytearray(64)
        report[0] = 1
        report[1] = 1
        report[2] = 7
        report[3:5] = (300).to_bytes(2, 'little')
        report[5:7] = (2000).to_bytes(2, 'little')
        self.assertEqual(tracker.feed(report), [('down', (300, 2000))])
        self.assertEqual(tracker.feed(report), [])
        self.assertEqual(tracker.feed(bytes([1])+bytes(63)), [('up', (300, 2000))])
        self.assertEqual(position((0, 4096), 270, 960, 360), (959, 359))
        self.assertEqual(coalesce([('move', (1, 2)), ('move', (3, 4)), ('up', (3, 4))]), [('move', (3, 4)), ('up', (3, 4))])
        self.assertEqual(tracker.feed(b'\x01'), [])

    def test_sensor_packet(self):
        from myth_sensors import packets
        raw = bytearray(4096)
        payload = json.dumps(dict(type='SENSOR', cpu_temp=42, cpu_fan=1200, gpu_temp=999)).encode()
        raw[48:52] = b'GAPP'
        raw[60:64] = len(payload).to_bytes(4, 'little')
        raw[64:64+len(payload)] = payload
        self.assertEqual(packets(raw)[0][1], dict(cpu_temp=42, cpu_fan=1200))
        raw[60:64] = (2000).to_bytes(4, 'little')
        self.assertEqual(packets(raw), {})

    def test_blank_key(self):
        with self.assertRaises(ValueError):
            store.upsert_profile(store.default_config(), 'test', 'https://example.com', '   ')

    def test_appearance(self):
        import app
        client = app.app.test_client()
        options = dict(base_url='http://127.0.0.1:8765', headers={'X-AC-Token': app.token})
        with patch.dict(app.cfg, theme='graphite', screen_layout='overview', background_opacity=16), patch('app.save_config') as save:
            result = client.post('/api/appearance', json=dict(theme='ice', screen_layout='clock'), **options)
            self.assertEqual(result.status_code, 200)
            self.assertEqual(app.cfg['theme'], 'ice')
            self.assertEqual(app.cfg['screen_layout'], 'clock')
            save.assert_called_once()
            for data in [dict(theme='bad'), dict(screen_layout='bad'), dict(background_opacity=51), dict(background_opacity='20')]:
                self.assertEqual(client.post('/api/appearance', json=data, **options).status_code, 400)
            html = client.get('/screen?preview=1&theme=amber&layout=dashboard', base_url=options['base_url']).text
            self.assertIn('data-theme="amber"', html)
            self.assertEqual(app.cfg['theme'], 'ice')

    def test_dpapi(self):
        value = 'test-only-secret'
        cipher = store.protect(value)
        self.assertNotIn(value, cipher)
        self.assertEqual(store.unprotect(cipher), value)

    def test_ccs_roundtrip(self):
        p = dict(name='测试中转站', base_url='https://example.com/v1')
        parsed = parse_ccs(ccs_link(p, 'test-key'))
        self.assertEqual(parsed, dict(p, api_key='test-key'))

    def test_untrusted_import(self):
        for link in ['https://example.com', 'ccswitch://v1/import?resource=script', 'ccswitch://v1/import?resource=provider&endpoint=http://bad&apiKey=k']:
            with self.assertRaises(ValueError):
                parse_ccs(link)

    def test_endpoint(self):
        for url in ['http://example.com', 'https://user:pass@example.com', 'https://example.com?a=1']:
            with self.assertRaises(ValueError):
                endpoint_url(url)

    def test_missing_is_not_zero(self):
        self.assertIsNone(summary({})['remaining'])
        self.assertEqual(summary({'remaining': 0})['remaining'], 0)
        self.assertEqual(summary({'remaining': -1})['remaining'], -1)

    def test_subscription(self):
        s = summary({'remaining': 25, 'subscription': {'weekly_limit_usd': 100, 'weekly_usage_usd': 75}})
        self.assertEqual(s['windows'][0]['remaining'], 25)

    def test_public_config(self):
        c = dict(profiles=[dict(id='x', api_key_protected='secret')])
        self.assertNotIn('secret', json.dumps(store.public_config(c)))

    def test_security_and_power(self):
        import app
        client = app.app.test_client()
        host = 'http://127.0.0.1:8765'
        self.assertEqual(client.get('/api/state', base_url='http://evil.test').status_code, 403)
        self.assertEqual(client.post('/api/refresh', base_url=host).status_code, 403)
        headers = {'X-AC-Token': app.token}
        with patch('app.subprocess.Popen') as run:
            p = client.post('/api/power/prepare', json={'command': 'shutdown'}, headers=headers, base_url=host).json
            r = client.post('/api/power/confirm', json=p, headers=headers, base_url=host)
            self.assertEqual(r.status_code, 400)
            run.assert_not_called()
            p = client.post('/api/power/prepare', json={'command': 'restart'}, headers=headers, base_url=host).json
            app.power_intent['time'] -= 6
            self.assertEqual(client.post('/api/power/confirm', json=p, headers=headers, base_url=host).status_code, 200)
            run.assert_called_once()
            self.assertEqual(client.post('/api/power/confirm', json=p, headers=headers, base_url=host).status_code, 400)


if __name__ == '__main__':
    unittest.main()
