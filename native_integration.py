"""User-level Windows desktop registration. Never changes an association implicitly."""
import json
import winreg
from pathlib import Path
from config_store import APP_DIR

ROOT = Path(__file__).resolve().parent
EXE = ROOT/'dist'/'ACQuotaScreen'/'ACQuotaScreen.exe'
BACKUP = APP_DIR/'protocol-backup.json'
RUN = r'Software\Microsoft\Windows\CurrentVersion\Run'
PROTOCOL = r'Software\Classes\ccswitch\shell\open\command'


def read(path, name=''):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,path) as key:
            return winreg.QueryValueEx(key,name)[0]
    except FileNotFoundError:
        return None


def write(path, name, value):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,path) as key:
        winreg.SetValueEx(key,name,0,winreg.REG_SZ,value)


def command():
    if not EXE.exists():
        raise ValueError('桌面程序尚未构建完成')
    return f'"{EXE}"'


def settings():
    cmd = read(PROTOCOL) or ''
    return dict(installed=EXE.exists(), autostart=read(RUN,'ACQuotaScreen') is not None,
                ccs_default=str(EXE).lower() in cmd.lower())


def configure(data):
    cmd=command()
    if 'autostart' in data:
        if data['autostart'] is True:
            write(RUN,'ACQuotaScreen',cmd+' --background')
        else:
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER,RUN,0,winreg.KEY_SET_VALUE) as key:
                    winreg.DeleteValue(key,'ACQuotaScreen')
            except FileNotFoundError:
                pass
    if data.get('ccs_default') is True:
        if not settings()['ccs_default']:
            BACKUP.write_text(json.dumps({'command':read(PROTOCOL)}),encoding='utf-8')
        write(r'Software\Classes\ccswitch','','URL:CC-Switch configuration')
        write(r'Software\Classes\ccswitch','URL Protocol','')
        write(PROTOCOL,'',cmd+' "%1"')
    elif data.get('ccs_default') is False and settings()['ccs_default']:
        old=json.loads(BACKUP.read_text(encoding='utf-8')).get('command') if BACKUP.exists() else None
        if old:
            write(PROTOCOL,'',old)
        else:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,PROTOCOL,0,winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key,'')
    return settings()


def register_candidate():
    cmd=command()
    write(r'Software\Classes\ACQuotaScreen.CCS','','AC 副屏配置导入')
    write(r'Software\Classes\ACQuotaScreen.CCS','URL Protocol','')
    write(r'Software\Classes\ACQuotaScreen.CCS\shell\open\command','',cmd+' "%1"')
    write(r'Software\ACQuotaScreen\Capabilities','ApplicationName','AC 副屏')
    write(r'Software\ACQuotaScreen\Capabilities','ApplicationDescription','机箱副屏与中转站额度')
    write(r'Software\ACQuotaScreen\Capabilities\URLAssociations','ccswitch','ACQuotaScreen.CCS')
    write(r'Software\RegisteredApplications','AC 副屏',r'Software\ACQuotaScreen\Capabilities')
