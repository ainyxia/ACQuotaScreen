import base64
import json
import threading
import time
from urllib.parse import urlsplit, parse_qs, urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler


def endpoint_url(base):
    u = urlsplit(base.strip().rstrip('/'))
    if u.scheme != 'https' or not u.hostname or u.username or u.password or u.query or u.fragment:
        raise ValueError('请填写不含账号和查询参数的 HTTPS 地址')
    return base.strip().rstrip('/')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def query_usage(base, key):
    base = endpoint_url(base)
    url = base + ('/usage' if base.endswith('/v1') else '/v1/usage')
    req = Request(url, headers={'Authorization': 'Bearer ' + key, 'Accept': 'application/json'})
    with build_opener(NoRedirect).open(req, timeout=15) as r:
        raw = r.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ValueError('接口响应过大')
    data = json.loads(raw)
    if not isinstance(data, dict) or not any(k in data for k in ('remaining', 'quota', 'subscription', 'balance', 'rate_limits')):
        raise ValueError('不是受支持的 Sub2API 额度响应')
    return data


def parse_ccs(link):
    if len(link) > 100000:
        raise ValueError('导入链接过长')
    u = urlsplit(link.strip())
    if (u.scheme, u.netloc, u.path) != ('ccswitch', 'v1', '/import'):
        raise ValueError('需要 ccswitch://v1/import 链接')
    q = parse_qs(u.query)
    def field(k, default=''):
        if len(q.get(k, [])) > 1:
            raise ValueError('重复导入字段')
        return q.get(k, [default])[0]
    if field('resource') != 'provider':
        raise ValueError('仅支持中转站配置')
    key = field('apiKey')
    if not key or '\n' in key or '\r' in key:
        raise ValueError('缺少有效密钥')
    return dict(name=field('name', 'Sub2API'), base_url=endpoint_url(field('endpoint')), api_key=key)


def ccs_link(profile, key):
    base = endpoint_url(profile['base_url'])
    path = '/usage' if base.endswith('/v1') else '/v1/usage'
    script = '({request:{url:"{{baseUrl}}' + path + '",method:"GET",headers:{Authorization:"Bearer {{apiKey}}"}},extractor:function(r){return {isValid:r.isValid,planName:r.planName,remaining:r.remaining,unit:r.unit}}})'
    return 'ccswitch://v1/import?' + urlencode(dict(resource='provider', app='codex', model='gpt-5.5', name=profile['name'], homepage=base, endpoint=base, apiKey=key, configFormat='json', usageEnabled='true', usageScript=base64.b64encode(script.encode()).decode(), usageAutoInterval='30'))


def summary(data):
    windows = []
    sub = data.get('subscription') or {}
    for period, name in [('daily', '每日'), ('weekly', '每周'), ('monthly', '每月')]:
        limit, used = sub.get(period + '_limit_usd'), sub.get(period + '_usage_usd')
        if isinstance(limit, (float, int)) and limit > 0 and isinstance(used, (float, int)):
            windows.append(dict(name=name, limit=limit, used=used, remaining=max(0, limit-used)))
    if data.get('quota'):
        windows.append(dict(name='密钥总额度', **data['quota']))
    for w in data.get('rate_limits', []):
        windows.append(dict(name=w.get('window', ''), **w))
    return dict(remaining=data.get('remaining', data.get('balance')), plan=data.get('planName', '密钥额度'), unit=data.get('unit', 'USD'), windows=windows, expires=sub.get('expires_at', data.get('expires_at')), today=sub.get('daily_usage_usd'), usage=data.get('usage', {}), valid=data.get('isValid', True), status=data.get('status', 'active'))
