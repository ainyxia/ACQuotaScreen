"""Register the built desktop app without enabling autostart or replacing CCS."""
import json
import subprocess
from config_store import APP_DIR
from native_integration import ROOT, EXE, register_candidate

if __name__ == '__main__':
    APP_DIR.mkdir(parents=True,exist_ok=True)
    (APP_DIR/'install.json').write_text(json.dumps({'root':str(ROOT)}),encoding='utf-8')
    register_candidate()
    print('Desktop registered. Existing CCS association and startup preference preserved.')
