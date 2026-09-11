import ctypes
import io
import json
import logging
import os
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import time
import uuid
from urllib.error import HTTPError
from urllib.parse import urlsplit

import psutil
from flask import Flask, request, jsonify, render_template, send_from_directory, abort, Response
from werkzeug.serving import make_server
from config_store import APP_DIR, MEDIA_DIR, THEME_PATH, load_config, save_config, public_config, active_profile, upsert_profile, unprotect
from service import query_usage, summary, parse_ccs, ccs_link, endpoint_url

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024
cfg = load_config()
lock = threading.RLock()
token = secrets.token_urlsafe(32)
wake = threading.Event()
state = {'quota': None, 'error': '尚未查询', 'updated': None, 'hardware': {}, 'usb': '未启动', 'touch': '未启动', 'page': 'quota', 'theme_version': 0}
usb_stop = threading.Event()
usb_thread = None
power_intent = None
PORT = 8765
THEMES = ('graphite', 'ice', 'amber', 'lime', 'spider')
LAYOUTS = ('overview', 'dashboard', 'clock')
pending_import = None
desktop_show_version = 0


@app.get('/api/desktop/events')
def desktop_events():
    with lock:
        pending = pending_import
        if pending and time.monotonic()-pending['time'] > 300:
            pending = None
        return jsonify(show_version=desktop_show_version, pending=None if not pending else
                       dict(id=pending['id'], name=pending['profile']['name'], base_url=pending['profile']['base_url']))


@app.post('/api/desktop/show')
def desktop_show():
    global desktop_show_version
    with lock:
        desktop_show_version += 1
    return jsonify(ok=True)


@app.post('/api/desktop/quit')
def desktop_quit():
    usb_stop.set()
    if 'server' in globals():
        threading.Timer(1, server.shutdown).start()
    return jsonify(ok=True)


@app.post('/api/desktop/import')
def desktop_import():
    global pending_import, desktop_show_version
    parsed = parse_ccs(request.get_json().get('link',''))
    with lock:
        pending_import = dict(id=secrets.token_hex(16), profile=parsed, time=time.monotonic())
        desktop_show_version += 1
    return jsonify(ok=True)


@app.post('/api/desktop/import/<action>')
def desktop_import_confirm(action):
    global pending_import
    with lock:
        pending = pending_import
        if not pending or pending['id'] != request.get_json().get('id') or time.monotonic()-pending['time'] > 300:
            raise ValueError('导入请求已失效')
        if action == 'confirm':
            pid = upsert_profile(cfg, **pending['profile'])
            save_config(cfg)
        elif action != 'cancel':
            abort(404)
        pending_import = None
    wake.set()
    return jsonify(ok=True)


@app.route('/api/desktop/settings', methods=['GET','POST'])
def desktop_settings():
    from native_integration import settings, configure
    return jsonify(configure(request.get_json()) if request.method == 'POST' else settings())


@app.before_request
def guard():
    if request.host != f'127.0.0.1:{PORT}':
        abort(403)
    if request.method != 'GET':
        if not secrets.compare_digest(request.headers.get('X-AC-Token', ''), token):
            abort(403)
        origin = request.headers.get('Origin')
        if origin and origin != f'http://127.0.0.1:{PORT}':
            abort(403)


@app.after_request
def headers(r):
    r.headers['Cache-Control'] = 'no-store'
    r.headers['X-Content-Type-Options'] = 'nosniff'
    r.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; media-src 'self'; font-src 'self'; connect-src 'self'; frame-ancestors 'self'; base-uri 'none'; form-action 'self'"
    return r


@app.errorhandler(ValueError)
def bad(e):
    return jsonify(error=str(e)), 400


@app.get('/')
def home():
    return render_template('index.html', token=token)


@app.get('/screen')
def screen():
    preview = request.args.get('preview') == '1'
    theme = request.args.get('theme', cfg['theme']) if preview else cfg['theme']
    layout = request.args.get('layout', cfg['screen_layout']) if preview else cfg['screen_layout']
    return render_template('screen.html', token=token, preview=preview,
                           theme=theme if theme in THEMES else 'graphite',
                           layout=layout if layout in LAYOUTS else 'overview')


@app.post('/api/appearance')
def appearance():
    d = request.get_json()
    with lock:
        theme = d.get('theme', cfg['theme'])
        layout = d.get('screen_layout', cfg['screen_layout'])
        opacity = d.get('background_opacity', cfg['background_opacity'])
        if theme not in THEMES or layout not in LAYOUTS:
            raise ValueError('未知主题或布局')
        if type(opacity) is not int or not 0 <= opacity <= 50:
            raise ValueError('背景强度应在 0 到 50 之间')
        cfg.update(theme=theme, screen_layout=layout, background_opacity=opacity)
        if 'motion_enabled' in d:
            cfg['motion_enabled'] = d['motion_enabled'] is True
        if 'status_light_enabled' in d:
            cfg['status_light_enabled'] = d['status_light_enabled'] is True
        save_config(cfg)
    return jsonify(ok=True)


@app.get('/api/state')
def get_state():
    with lock:
        return jsonify(**state, config=public_config(cfg))


@app.post('/api/profile')
def profile():
    d = request.get_json()
    with lock:
        endpoint_url(d.get('base_url', ''))
        pid = upsert_profile(cfg, d.get('name', ''), d['base_url'], d.get('api_key', ''), d.get('id') or None)
        save_config(cfg)
    wake.set()
    return jsonify(id=pid)


@app.post('/api/import')
def import_link():
    d = parse_ccs(request.get_json().get('link', ''))
    with lock:
        pid = upsert_profile(cfg, **d)
        save_config(cfg)
    return jsonify(id=pid)


@app.post('/api/profile/<pid>/<action>')
def profile_action(pid, action):
    with lock:
        p = next((dict(p) for p in cfg['profiles'] if p['id'] == pid), None)
        if not p:
            abort(404)
        if action == 'activate':
            cfg['active_profile_id'] = pid
            state.update(quota=None, updated=None, error='正在查询')
            save_config(cfg)
            wake.set()
        elif action == 'delete':
            cfg['profiles'] = [p for p in cfg['profiles'] if p['id'] != pid]
            if cfg['active_profile_id'] == pid:
                cfg['active_profile_id'] = cfg['profiles'][0]['id'] if cfg['profiles'] else None
                state.update(quota=None, updated=None, error='正在查询')
            save_config(cfg)
            wake.set()
        elif action == 'ccs':
            return jsonify(link=ccs_link(p, unprotect(p['api_key_protected'])))
        elif action != 'test':
            abort(404)
    if action == 'test':
        try:
            data = query_usage(p['base_url'], unprotect(p['api_key_protected']))
            return jsonify(message='连接成功', quota=summary(data))
        except Exception as e:
            return jsonify(error=safe_error(e)), 400
    return jsonify(ok=True)


def safe_error(e):
    if isinstance(e, HTTPError):
        return f'中转站返回 HTTP {e.code}'
    if isinstance(e, ValueError):
        return '接口数据格式不受支持'
    return '连接失败或超时，请检查地址和密钥'


@app.post('/api/settings')
def settings():
    d = request.get_json()
    with lock:
        source = d.get('active_source', cfg.get('active_source', 'relay'))
        if source not in ('relay', 'official'):
            raise ValueError('未知额度数据源')
        if source != cfg.get('active_source'):
            cfg['active_source'] = source
            state.update(quota=None, updated=None, error='正在切换数据源')
        cfg['refresh_seconds'] = max(15, min(3600, int(d.get('refresh_seconds', 30))))
        rotation = int(d.get('screen_rotation', 270))
        if rotation not in (0, 90, 180, 270):
            raise ValueError('无效方向')
        cfg['screen_rotation'] = rotation
        cfg['custom_text'] = str(d.get('custom_text', ''))[:120]
        cfg['hour12'] = bool(d.get('hour12'))
        cfg['shortcuts'] = [dict(name=str(s['name'])[:40], path=str(s['path'])) for s in d.get('shortcuts', [])][:8]
        save_config(cfg)
    wake.set()
    return jsonify(ok=True)

@app.post('/api/source')
def source():
    d = request.get_json() or {}
    value = d.get('source')
    if value not in ('relay', 'official'):
        raise ValueError('未知额度数据源')
    with lock:
        cfg['active_source'] = value
        state.update(quota=None, updated=None, error='正在查询')
        save_config(cfg)
    wake.set()
    return jsonify(ok=True)

@app.post('/api/upload/<kind>')
def upload(kind):
    f = request.files.get('file')
    if not f:
        raise ValueError('请选择文件')
    ext = Path(f.filename).suffix.lower()
    if kind == 'css':
        raw = f.read(256001)
        if ext != '.css' or len(raw) > 256000:
            raise ValueError('请选择小于 256KB 的 CSS 文件')
        text = raw.decode('utf-8-sig')
        THEME_PATH.write_text(text, encoding='utf-8')
        state['theme_version'] += 1
    elif kind == 'media' and ext in ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.mp4', '.webm'):
        MEDIA_DIR.mkdir(parents=True, exist_ok=True)
        name = uuid.uuid4().hex + ext
        f.save(MEDIA_DIR / name)
        with lock:
            cfg['background_media'] = name
            save_config(cfg)
    else:
        raise ValueError('不支持的文件类型')
    return jsonify(ok=True)


@app.post('/api/reset/<kind>')
def reset(kind):
    if kind == 'css':
        THEME_PATH.write_text('', encoding='utf-8')
        state['theme_version'] += 1
    elif kind == 'media':
        with lock:
            cfg['background_media'] = ''
            save_config(cfg)
    else:
        abort(404)
    return jsonify(ok=True)


@app.get('/theme.css')
def css():
    return Response(THEME_PATH.read_text(encoding='utf-8') if THEME_PATH.exists() else '', mimetype='text/css')


@app.get('/media/<name>')
def media(name):
    return send_from_directory(MEDIA_DIR, name)


@app.post('/api/refresh')
def refresh():
    wake.set()
    return jsonify(ok=True)


@app.post('/api/page')
def page():
    p = request.get_json()['page']
    if p not in ('quota', 'hardware', 'control'):
        abort(400)
    state['page'] = p
    return jsonify(ok=True)


@app.post('/api/power/<action>')
def power(action):
    global power_intent
    if action == 'cancel':
        power_intent = None
    elif action == 'prepare':
        command = request.get_json().get('command')
        if command not in ('shutdown', 'restart', 'sleep'):
            abort(400)
        power_intent = {'id': secrets.token_hex(16), 'command': command, 'time': time.monotonic()}
        return jsonify(id=power_intent['id'])
    elif action == 'confirm':
        p = power_intent
        power_intent = None
        if not p or request.get_json().get('id') != p['id'] or not 5 <= time.monotonic()-p['time'] <= 30:
            raise ValueError('确认已失效，请重试')
        if p['command'] == 'sleep':
            threading.Timer(0.5, lambda: ctypes.windll.powrprof.SetSuspendState(False, False, False)).start()
        else:
            subprocess.Popen(['shutdown.exe', '/s' if p['command'] == 'shutdown' else '/r', '/t', '0'], creationflags=0x08000000)
    else:
        abort(404)
    return jsonify(ok=True)


@app.post('/api/shortcut/<int:index>')
def shortcut(index):
    with lock:
        items = cfg.get('shortcuts', [])
        if not 0 <= index < len(items):
            abort(404)
        path = Path(items[index]['path'])
    if not path.is_absolute() or not path.is_file() or path.suffix.lower() not in ('.exe', '.lnk'):
        raise ValueError('需要有效的本机 EXE 或快捷方式路径')
    os.startfile(str(path))
    return jsonify(ok=True)


def poll():
    while True:
        wake.clear()
        with lock:
            source = cfg.get('active_source', 'relay')
            p = active_profile(cfg) if source == 'relay' else None
            p = dict(p) if p else None
            delay = cfg['refresh_seconds']
        if source == 'official':
            try:
                from official_quota import OfficialQuota
                if not hasattr(poll, '_official_reader'): poll._official_reader = OfficialQuota()
                result = poll._official_reader.sample()
                with lock:
                    if cfg.get('active_source') != 'official':
                        pass
                    elif result:
                        state.update(quota=result, error='' if result.get('status') != 'waiting_refresh' else '官方额度已到重置时间，等待新额度同步', updated=time.time())
                    else: state.update(quota=None, error='等待官方 Codex 额度数据', updated=None)
            except Exception:
                with lock: state.update(quota=None, error='读取官方 Codex 额度失败', updated=None)
        elif p:
            try:
                result = summary(query_usage(p['base_url'], unprotect(p['api_key_protected'])))
                with lock:
                    if cfg.get('active_source') == 'relay' and cfg['active_profile_id'] == p['id']:
                        state.update(quota=result, error='', updated=time.time())
            except Exception as e:
                with lock:
                    if cfg.get('active_source') == 'relay' and cfg['active_profile_id'] == p['id']:
                        state['error'] = safe_error(e)
        elif source == 'relay':
            state.update(quota=None, updated=None, error='请添加中转站')
        wake.wait(delay)


def codex_activity():
    from codex_status import CodexStatus
    watcher = None
    source_seen = None
    while True:
        try:
            source = cfg.get('active_source', 'relay')
            if source != source_seen:
                watcher = CodexStatus(Path.home()/('.codex-official' if source == 'official' else '.codex'))
                source_seen = source
            state['codex'] = watcher.sample()
        except Exception:
            state['codex'] = watcher.result('unknown', 0, 0)
        time.sleep(1)


def hardware():
    from myth_sensors import MythSensors
    myth = MythSensors()
    prev, stamp = psutil.net_io_counters(), time.monotonic()
    psutil.cpu_percent()
    while True:
        time.sleep(2)
        now, net = time.monotonic(), psutil.net_io_counters()
        mem = psutil.virtual_memory()
        info = dict(cpu=psutil.cpu_percent(), memory=mem.percent, memory_used=mem.used/2**30,
                    upload=max(0, net.bytes_sent-prev.bytes_sent)/(now-stamp)/2**20,
                    download=max(0, net.bytes_recv-prev.bytes_recv)/(now-stamp)/2**20)
        prev, stamp = net, now
        try:
            r = subprocess.run(['nvidia-smi', '--query-gpu=temperature.gpu,utilization.gpu,memory.used,memory.total,power.draw', '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=2, creationflags=0x08000000)
            values = r.stdout.splitlines()[0].split(',')
            for name, value in zip(('gpu_temp', 'gpu', 'vram', 'vram_total', 'gpu_power'), values):
                try:
                    info[name] = float(value)
                except ValueError:
                    pass
        except Exception:
            pass
        extra, source = myth.sample()
        info.update(extra)
        info['sensor_source'] = source
        state['hardware'] = info


def usb_worker():
    from playwright.sync_api import sync_playwright
    from PIL import Image
    from msdisplay import MSDisplay
    from touch_input import TouchTracker, position, coalesce
    display = None
    touch = None
    try:
        if any(p.info['name'].lower() == 'mythcool.exe' for p in psutil.process_iter(['name']) if p.info['name']):
            state['usb'] = '请先退出 Myth.Cool，避免争用副屏'
            return
        display = MSDisplay()
        display.initialize()
        try:
            import hid
            touch = hid.device()
            touch.open(0x374A, 0xA401)
            touch.set_nonblocking(1)
            state['touch'] = '触控接口已打开，尚未收到触摸报告'
            state['touch_reports'] = 0
            state['touch_clicks'] = 0
            state['touch_last'] = None
        except Exception:
            touch = None
            state['touch'] = 'Windows 未允许读取触摸；可用电脑端切页'
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel='msedge', headless=True)
            rotation = cfg.get('screen_rotation', 270)
            size = {'width': 960, 'height': 360} if rotation in (90, 270) else {'width': 360, 'height': 960}
            page = browser.new_page(viewport=size)
            page.goto(f'http://127.0.0.1:{PORT}/screen')
            pressed = False
            tracker = TouchTracker()
            while not usb_stop.is_set():
                if rotation != cfg.get('screen_rotation', 270):
                    rotation = cfg['screen_rotation']
                    size = {'width': 960, 'height': 360} if rotation in (90, 270) else {'width': 360, 'height': 960}
                    page.set_viewport_size(size)
                if touch:
                    events = []
                    for _ in range(256):
                        report = touch.read(64)
                        if not report:
                            break
                        state['touch_reports'] += 1
                        events.extend(tracker.feed(report))
                    for action, point in coalesce(events):
                        x, y = position(point, rotation, size['width'], size['height'])
                        state['touch_last'] = dict(x=x, y=y, action=action)
                        if action != 'up':
                            page.mouse.move(x, y)
                        if action == 'down' and not pressed:
                            page.mouse.down()
                            pressed = True
                        elif action == 'up' and pressed:
                            page.mouse.up()
                            pressed = False
                            state['touch_clicks'] += 1
                    if state['touch_reports']:
                        state['touch'] = f"触控报告 {state['touch_reports']} · 点按 {state['touch_clicks']}"
                image = Image.open(io.BytesIO(page.screenshot())).convert('RGB')
                if rotation:
                    image = image.rotate(rotation, expand=True)
                display.send_rgb(image.tobytes())
                state['usb'] = '帧已发送 ' + time.strftime('%H:%M:%S')
                usb_stop.wait(0.12)
            browser.close()
    except Exception as e:
        logging.exception('USB display worker failed')
        state['usb'] = '副屏输出失败: ' + type(e).__name__ + ' ' + str(e).splitlines()[0][:180]
    finally:
        if touch:
            touch.close()
        if display:
            display.close()


@app.post('/api/usb/<action>')
def usb(action):
    global usb_thread
    if action == 'stop':
        usb_stop.set()
        state['usb'] = '正在停止'
    elif action == 'start':
        if not usb_thread or not usb_thread.is_alive():
            usb_stop.clear()
            usb_thread = threading.Thread(target=usb_worker, daemon=True)
            usb_thread.start()
    else:
        abort(404)
    return jsonify(ok=True)


if __name__ == '__main__':
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateMutexW.restype = ctypes.c_void_p
    instance_mutex = kernel.CreateMutexW(None, False, 'Local\\ACQuotaScreen')
    if not instance_mutex:
        raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error() == 183:
        sys.exit(0)
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    for port in range(8765, 8785):
        try:
            server = make_server('127.0.0.1', port, app, threaded=True)
            PORT = port
            break
        except SystemExit:
            continue
    else:
        raise RuntimeError('没有可用端口')
    (APP_DIR / 'runtime.json').write_text(json.dumps({'port': PORT, 'pid': os.getpid()}))
    threading.Thread(target=poll, daemon=True).start()
    threading.Thread(target=hardware, daemon=True).start()
    threading.Thread(target=codex_activity, daemon=True).start()
    server.serve_forever()
