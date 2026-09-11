from __future__ import annotations

import glob
import os
import struct
import time
from pathlib import Path

import hid
import usb.backend.libusb0
import usb.core
import usb.util


VID = 0x345F
PID = 0x9132
INTERFACE_VIDEO = 3
EP_OUT = 0x04
WIDTH = 360
HEIGHT = 960
COLOR_BGR888 = 0x11
VIC_360X960 = 0xA0

STATUS_9132 = {
    "power": 0xC454, "transfer_mode": 0x1026, "video_in": 0x1123,
    "video_out": 0x1125, "video_on": 0x118D, "trans": 0x118D,
}
STATUS_OTHER = {
    "power": 0xC454, "transfer_mode": 0xC558, "video_in": 0xC555,
    "video_out": 0xC557, "video_on": 0xC555, "trans": 0xC555,
}


def find_libusb0() -> str:
    local = os.environ.get("LOCALAPPDATA", "")
    pattern = str(Path(local) / "MythCool" / "Apps" / "main*" / "*" / "win32" / "libusb" / "amd64" / "libusb0.dll")
    matches = sorted(glob.glob(pattern), reverse=True)
    if not matches:
        raise RuntimeError("没有找到 Myth.Cool 自带的 64 位 libusb0.dll")
    return matches[0]


class MSDisplay:
    def __init__(self) -> None:
        hid_entries = hid.enumerate(VID, PID)
        if not hid_entries:
            raise RuntimeError("没有找到副屏 HID 控制接口")
        self.hid = hid.device()
        self.hid.open_path(hid_entries[0]["path"])

        dll = find_libusb0()
        backend = usb.backend.libusb0.get_backend(find_library=lambda _: dll)
        self.video = usb.core.find(idVendor=VID, idProduct=PID, backend=backend)
        if self.video is None:
            self.hid.close()
            raise RuntimeError("没有找到副屏 USB 视频接口")
        try:
            usb.util.claim_interface(self.video, INTERFACE_VIDEO)
        except usb.core.USBError as exc:
            self.hid.close()
            raise RuntimeError("副屏正被 Myth.Cool 占用，请先退出 Myth.Cool") from exc
        try:
            self.video.clear_halt(EP_OUT)
        except usb.core.USBError:
            pass
        self.status = STATUS_OTHER
        self.chip_id = 0
        self.video_port = 6
        self.next_fid = 1
        self.output_enabled = False

    def close(self) -> None:
        try:
            usb.util.release_interface(self.video, INTERFACE_VIDEO)
        except Exception:
            pass
        try:
            usb.util.dispose_resources(self.video)
        except Exception:
            pass
        try:
            self.hid.close()
        except Exception:
            pass

    def _hid_set(self, payload: bytes | bytearray | list[int]) -> None:
        data = bytes(payload)[:8].ljust(8, b"\x00")
        written = self.hid.send_feature_report(b"\x00" + data)
        if written <= 0:
            raise RuntimeError("HID 写入失败")

    def _hid_get(self) -> bytes:
        data = bytes(self.hid.get_feature_report(0, 9))
        if len(data) == 9 and data[0] == 0:
            data = data[1:]
        if len(data) < 8:
            raise RuntimeError("HID 读取失败")
        return data[:8]

    def xdata_read(self, address: int) -> int:
        self._hid_set([0xB5, address >> 8, address & 0xFF])
        return self._hid_get()[3]

    def xdata_read_n(self, address: int, count: int) -> bytes:
        result = bytearray()
        for offset in range(0, count, 4):
            addr = address + offset
            self._hid_set([0xB5, addr >> 8, addr & 0xFF])
            result.extend(self._hid_get()[3:7])
        return bytes(result[:count])

    def xdata_write(self, address: int, value: int) -> None:
        self._hid_set([0xB6, address >> 8, address & 0xFF, value & 0xFF])

    def _wait_zero(self, address: int, timeout: float = 1.5) -> None:
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if self.xdata_read(address) == 0:
                return
            time.sleep(0.002)
        raise RuntimeError(f"副屏命令超时: 0x{address:04X}")

    def _command(self, payload: list[int], status_key: str | None, settle: float = 0.01) -> None:
        self._hid_set(payload)
        time.sleep(settle)
        if status_key:
            self._wait_zero(self.status[status_key])

    def identify(self) -> None:
        chip_f = self.xdata_read_n(0xF000, 3)
        chip_ff = self.xdata_read_n(0xFF00, 3)
        if len(chip_f) == 3 and chip_f[1:] == b"\x16\x0a":
            self.chip_id = {0xB7: 0x912C, 0xA7: 0x912A}.get(chip_f[0], 0x9120)
        if len(chip_ff) == 3 and chip_ff[1:] == b"\x13\x0a":
            self.chip_id = 0x9132
        if not self.chip_id:
            raise RuntimeError('未知副屏芯片，停止初始化')
        self.status = STATUS_9132 if self.chip_id == 0x9132 else STATUS_OTHER
        self.video_port = self.xdata_read(49) or 6

    def set_screen(self, enabled: bool) -> None:
        if self.chip_id == 0x9132:
            address, bit, invert = (0xFB07, 0x02, True) if self.video_port == 5 else (0xF037, 0x01, False)
        else:
            table = {5: (0xF507, 0x02, True), 2: (0xF004, 0x80, False), 3: (0xF030, 0x01, False), 6: (0xF005, 0x10, False)}
            address, bit, invert = table.get(self.video_port, (0xF004, 0x02, False))
        current = self.xdata_read(address)
        value = (current & ~bit) if (enabled == invert) else (current | bit)
        if value != current:
            self.xdata_write(address, value)

    def initialize(self) -> None:
        self.identify()
        self._command([0xA6, 0x03, 3], "transfer_mode")
        self.xdata_write(0xDEEE, 1)
        self._command([0xA6, 0x07, 1], "power", 0.1)
        self._command([0xA6, 0x05, 0], "video_on")
        self.set_screen(False)
        self._command([0xA6, 0x01, 0x01, 0x68, 0x03, 0xC0, COLOR_BGR888, 0], "video_in")
        self._command([0xA6, 0x02, VIC_360X960, 0, 0x01, 0x68, 0x03, 0xC0], "video_out", 0.02)
        self._command([0xA6, 0x04, 1], "trans")

    @staticmethod
    def encode_rgb(rgb: bytes) -> bytes:
        body = bytearray(len(rgb))
        body[0::3] = rgb[2::3]
        body[1::3] = rgb[1::3]
        body[2::3] = rgb[0::3]
        return bytes(body).replace(b"\xff", b"\xfe")

    def send_rgb(self, rgb: bytes) -> None:
        expected = WIDTH * HEIGHT * 3
        if len(rgb) != expected:
            raise ValueError(f"RGB 帧大小错误: {len(rgb)} != {expected}")
        header = bytearray(8)
        struct.pack_into("<I", header, 0, 0xFF)
        header[5] = WIDTH >> 4
        header[6] = ((WIDTH & 0x0F) << 4) | ((HEIGHT >> 8) & 0x0F)
        header[7] = HEIGHT & 0xFF
        frame = bytes(header) + self.encode_rgb(rgb) + bytes([0xFF, 0xC0, 0, 0, 0, 0, 0, 0])
        for offset in range(0, len(frame), 0x80000):
            chunk = frame[offset:offset + 0x80000]
            written = self.video.write(EP_OUT, chunk, timeout=12000)
            if written != len(chunk):
                raise RuntimeError('USB 帧未完整写入')
        self.video.write(EP_OUT, b"", timeout=12000)
        self._hid_set([0xA6, 0x00, self.next_fid, 100])
        self.next_fid ^= 1
        if not self.output_enabled:
            self.set_screen(True)
            self._command([0xA6, 0x05, 1], "video_on")
            self.output_enabled = True
