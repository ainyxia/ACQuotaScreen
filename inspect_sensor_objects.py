"""Read-only enumeration of hardware-related Windows named objects."""
import ctypes as c
from ctypes import wintypes as w


class UnicodeString(c.Structure):
    _fields_ = [('length', w.USHORT), ('maximum', w.USHORT), ('buffer', c.c_void_p)]


class Attributes(c.Structure):
    _fields_ = [('length', w.ULONG), ('root', w.HANDLE), ('name', c.POINTER(UnicodeString)),
                ('attributes', w.ULONG), ('security', c.c_void_p), ('qos', c.c_void_p)]


def names(path):
    buf = c.create_unicode_buffer(path)
    name = UnicodeString(len(path)*2, (len(path)+1)*2, c.cast(buf, c.c_void_p))
    attrs = Attributes(c.sizeof(Attributes), None, c.pointer(name), 0x40, None, None)
    handle = w.HANDLE()
    nt = c.WinDLL('ntdll')
    if nt.NtOpenDirectoryObject(c.byref(handle), 1, c.byref(attrs)) < 0:
        return
    context = w.ULONG()
    result = c.create_string_buffer(65536)
    size = w.ULONG()
    try:
        while nt.NtQueryDirectoryObject(handle, result, len(result), True, False, c.byref(context), c.byref(size)) >= 0:
            entry = (UnicodeString*2).from_buffer(result)
            label = c.wstring_at(entry[0].buffer, entry[0].length//2)
            kind = c.wstring_at(entry[1].buffer, entry[1].length//2)
            if 'HWNDInterface' not in label and any(s in label.lower() for s in ('hw', 'sensor', 'myth', 'gamepp', 'monitor', 'ipc')):
                print(path, kind, label)
    finally:
        nt.NtClose(handle)


if __name__ == '__main__':
    names('\\BaseNamedObjects')
    for session in range(5):
        names(f'\\Sessions\\{session}\\BaseNamedObjects')
