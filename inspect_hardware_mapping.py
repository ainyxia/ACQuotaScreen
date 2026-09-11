"""Inspect only the known hardware IPC mapping, without writing to it."""
import ctypes as c
from ctypes import wintypes as w
import re

k = c.WinDLL('kernel32', use_last_error=True)
k.OpenFileMappingW.argtypes = [w.DWORD, w.BOOL, w.LPCWSTR]
k.OpenFileMappingW.restype = w.HANDLE
k.MapViewOfFile.argtypes = [w.HANDLE, w.DWORD, w.DWORD, w.DWORD, c.c_size_t]
k.MapViewOfFile.restype = c.c_void_p
k.UnmapViewOfFile.argtypes = [c.c_void_p]
k.CloseHandle.argtypes = [w.HANDLE]


def read_mapping(name, size=4096):
    h = k.OpenFileMappingW(4, False, name)
    if not h:
        raise c.WinError(c.get_last_error())
    ptr = k.MapViewOfFile(h, 4, 0, 0, size)
    try:
        if not ptr:
            raise c.WinError(c.get_last_error())
        return c.string_at(ptr, size)
    finally:
        if ptr:
            k.UnmapViewOfFile(ptr)
        k.CloseHandle(h)


if __name__ == '__main__':
    for suffix in ('__AC_CONN__GAMEPP-IPC-Hardware-', '__QU_CONN__64__8__GAMEPP-IPC-Hardware-'):
        name = '__IPC_SHM__' + suffix
        raw = read_mapping(name)
        print(name, raw[:128].hex(), re.findall(rb'[ -~]{6,}', raw)[:20])
