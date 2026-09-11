import unittest
from unittest.mock import patch


class DesktopTests(unittest.TestCase):
    def test_import_requires_confirmation_and_redacts_key(self):
        import app
        from config_store import default_config
        client=app.app.test_client()
        host='http://127.0.0.1:8765'
        headers={'X-AC-Token':app.token}
        with patch.object(app,'pending_import',None),patch.object(app,'cfg',default_config()),patch('app.save_config') as save:
            uri='ccswitch://v1/import?resource=provider&app=codex&name=Test&endpoint=https%3A%2F%2Fexample.com&apiKey=test-only-key'
            r=client.post('/api/desktop/import',json={'link':uri},headers=headers,base_url=host)
            self.assertEqual(r.status_code,200)
            self.assertEqual(app.cfg['profiles'],[])
            save.assert_not_called()
            events=client.get('/api/desktop/events',base_url=host)
            self.assertNotIn('test-only-key',events.text)
            pending=events.json['pending']
            r=client.post('/api/desktop/import/confirm',json={'id':pending['id']},headers=headers,base_url=host)
            self.assertEqual(r.status_code,200)
            self.assertEqual(len(app.cfg['profiles']),1)
            self.assertNotIn('test-only-key',str(app.cfg))
            self.assertIsNone(app.pending_import)

    def test_startup_is_opt_in(self):
        import native_integration as native
        with patch.object(native,'read',return_value=None):
            self.assertFalse(native.settings()['autostart'])
            self.assertFalse(native.settings()['ccs_default'])


if __name__=='__main__':unittest.main()
