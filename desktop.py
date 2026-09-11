"""Native WebView2 host and tray. UI stays local; no external browser is opened."""
import ctypes
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import traceback
from urllib.request import urlopen, Request

APP_DIR=Path(os.environ['LOCALAPPDATA'])/'ACQuotaScreen'
APP_DIR.mkdir(parents=True, exist_ok=True)
ERROR_LOG=APP_DIR/'desktop-error.log'


def resolve_root():
    try:
        root=Path(json.loads((APP_DIR/'install.json').read_text(encoding='utf-8'))['root'])
        if (root/'app.py').is_file():
            return root
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        pass
    if getattr(sys, 'frozen', False):
        root=Path(sys.executable).resolve().parents[2]
    else:
        root=Path(__file__).resolve().parent
    if not (root/'app.py').is_file():
        raise FileNotFoundError(f'找不到本机服务文件: {root / "app.py"}')
    (APP_DIR/'install.json').write_text(json.dumps({'root':str(root)}), encoding='utf-8')
    return root


ROOT=resolve_root()


def connect():
    runtime=json.loads((APP_DIR/'runtime.json').read_text())
    port=int(runtime['port'])
    if not 8765 <= port <= 8784:
        raise ValueError('Invalid local port')
    url=f'http://127.0.0.1:{port}'
    with urlopen(url,timeout=2) as response:
        token=re.search(r'name="ac-token" content="([^"]+)"',response.read().decode()).group(1)
    return url,token


def post(url,token,path,data):
    request=Request(url+path,data=json.dumps(data).encode(),headers={'Content-Type':'application/json','X-AC-Token':token})
    with urlopen(request,timeout=5) as response:
        return json.load(response)


def main():
    try:
        url,token=connect()
    except Exception:
        python=ROOT.parent/'.venv'/'Scripts'/'pythonw.exe'
        if not python.is_file():
            raise FileNotFoundError(f'找不到 Python 运行环境: {python}')
        subprocess.Popen([str(python),str(ROOT/'app.py')],cwd=ROOT,creationflags=0x08000000)
        for _ in range(40):
            time.sleep(.25)
            try:
                url,token=connect()
                break
            except Exception:
                pass
        else:
            raise RuntimeError('本机服务启动失败')
    links=[arg for arg in sys.argv[1:] if arg.startswith('ccswitch:')]
    if links:
        post(url,token,'/api/desktop/import',{'link':links[0]})
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateMutexW.restype=ctypes.c_void_p
    mutex=kernel.CreateMutexW(None,False,'Local\\ACQuotaScreenDesktop')
    if ctypes.get_last_error()==183:
        post(url,token,'/api/desktop/show',{})
        return
    import webview
    import pystray
    from PIL import Image, ImageDraw
    image=Image.new('RGB',(64,64),'#10131c');draw=ImageDraw.Draw(image)
    draw.rounded_rectangle((8,12,56,49),radius=5,outline='#ff455c',width=4)
    draw.line((17,36,25,25,33,39,46,23),fill='#46d9f4',width=3)
    background='--background' in sys.argv and not links
    window=webview.create_window('AC 副屏',url,width=1280,height=880,min_size=(860,640),hidden=background)
    quitting=threading.Event()
    def show(*_):
        window.show();window.restore()
    def close():
        if not quitting.is_set():
            window.hide()
            return False
    def exit_app(*_):
        quitting.set()
        tray.stop()
        try:
            post(url,token,'/api/usb/stop',{})
            post(url,token,'/api/desktop/quit',{})
        except Exception:
            pass
        window.destroy()
    window.events.closing+=close
    tray=pystray.Icon('ACQuotaScreen',image,'AC 副屏',pystray.Menu(
        pystray.MenuItem('打开控制台',show,default=True),pystray.MenuItem('退出',exit_app)))
    def monitor():
        previous=None
        while not quitting.wait(1):
            try:
                with urlopen(url+'/api/desktop/events',timeout=2) as response:data=json.load(response)
                version=data['show_version']
                if previous is not None and version!=previous:show()
                previous=version
            except Exception:
                pass
    def started():
        threading.Thread(target=tray.run,daemon=True).start()
        threading.Thread(target=monitor,daemon=True).start()
        if not background:
            show()
        try:post(url,token,'/api/usb/start',{})
        except Exception:pass
    webview.start(started,gui='edgechromium',private_mode=True)


if __name__=='__main__':
    try:
        ERROR_LOG.unlink(missing_ok=True)
        main()
    except Exception as exc:
        ERROR_LOG.write_text(traceback.format_exc(), encoding='utf-8')
        message=f'启动失败：{exc}\n\n详细日志：{ERROR_LOG}'
        ctypes.windll.user32.MessageBoxW(None,message,'AC 副屏',0x10)
