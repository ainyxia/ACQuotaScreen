"""Read the observed Myth.Cool 1.0.1231 sensor broadcast without consuming IPC."""
import json
import math
import time
from inspect_hardware_mapping import read_mapping

MAPPING = '__IPC_SHM____CHUNK_INFO__1024'
FIELDS = {
    'cpu_temp': ('cpu_temp', -20, 150), 'cpu_fan': ('cpu_fan', 0, 20000),
    'cpu_freq': ('cpu_freq', 0, 15000), 'cpu_load': ('cpu', 0, 100),
    'gpu_temp': ('gpu_temp', -20, 150), 'gpu_load': ('gpu', 0, 100),
    'gpu_fan': ('gpu_fan', 0, 20000), 'gpu_freq': ('gpu_freq', 0, 15000),
    'mb_temp': ('mb_temp', -20, 150), 'mem_temp': ('mem_temp', -20, 150),
}


def packets(raw):
    found = {}
    # This installed version stores 1024-byte slots with a 64-byte envelope.
    for offset in range(0, len(raw)-1023, 1024):
        if raw[offset+48:offset+52] != b'GAPP':
            continue
        size = int.from_bytes(raw[offset+60:offset+64], 'little')
        if not 2 <= size <= 960:
            continue
        payload = raw[offset+64:offset+64+size].rstrip(b'\0')
        try:
            data = json.loads(payload)
        except (ValueError, UnicodeError):
            continue
        if isinstance(data, dict) and data.get('type') == 'SENSOR':
            values = {}
            for key, (name, low, high) in FIELDS.items():
                value = data.get(key)
                if type(value) in (int, float) and math.isfinite(value) and low <= value <= high:
                    values[name] = value
            if values:
                found[offset] = (payload, values)
    return found


class MythSensors:
    def __init__(self):
        self.previous = None
        self.latest = {}
        self.updated = 0

    def sample(self):
        now = time.monotonic()
        try:
            raw = read_mapping(MAPPING)
            # Reject a torn concurrent write instead of displaying mixed readings.
            if raw != read_mapping(MAPPING):
                return {}, 'Myth.Cool 数据更新中'
            current = packets(raw)
            if self.previous is not None:
                changed = [value for slot, value in current.items() if self.previous.get(slot) != value]
                if len(changed) == 1:
                    self.latest = changed[0][1]
                    self.updated = now
            self.previous = current
        except OSError:
            self.previous = None
            self.latest = {}
            return {}, 'Myth.Cool 数据源未连接'
        if self.updated and now-self.updated < 15:
            return dict(self.latest), 'Myth.Cool 实时传感器'
        return {}, 'Myth.Cool 等待新传感器数据'
