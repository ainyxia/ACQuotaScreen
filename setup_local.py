"""Optional local setup helper; credentials are entered in the control panel."""
from config_store import load_config

if __name__ == '__main__':
    cfg = load_config()
    print('已有中转站配置：', len(cfg.get('profiles', [])))
    print('请打开控制台，在“中转站”区域手动填写地址和 API Key。')
