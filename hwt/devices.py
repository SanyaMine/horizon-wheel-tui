"""Windows HID controller enumeration via SetupAPI (ctypes).

C# uses Windows.Gaming.Input; on Python we read the device list through SetupAPI, which
also gives us the VID/PID and a friendly name for the Step 1 role pickers.

CRITICAL: HDEVINFO is a pointer. Every SetupAPI function that returns or receives the
handle MUST declare restype/argtypes as c_void_p, or ctypes truncates the 64-bit handle
to a 32-bit int and enumeration silently returns nothing on 64-bit Windows.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass

from .vidpid import VidPid


@dataclass
class DeviceInfo:
    name: str
    vid_pid: VidPid
    instance_id: str
    class_name: str = ""
    manufacturer: str = ""

    def label(self) -> str:
        return f"{self.name}  [{self.vid_pid}]"


def get_controller_devices() -> list[DeviceInfo]:
    """Return present HID controller devices (Windows only; [] elsewhere)."""
    if sys.platform != "win32":
        return []
    try:
        return _win_enumerate()
    except Exception:
        return []


def _win_enumerate() -> list[DeviceInfo]:
    import ctypes
    from ctypes import byref, create_unicode_buffer

    DIGCF_PRESENT    = 0x02
    DIGCF_ALLCLASS   = 0x04
    SPDRP_DEVICEDESC = 0x00
    SPDRP_HWID       = 0x01
    SPDRP_CLASS      = 0x07
    SPDRP_MFG        = 0x0B
    SPDRP_FRIENDLY   = 0x0C
    INVALID_HANDLE   = ctypes.c_void_p(-1).value

    class _SPDD(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint32), ("ClassGuid", ctypes.c_byte * 16),
                    ("DevInst", ctypes.c_uint32), ("Reserved", ctypes.c_size_t)]

    api = ctypes.WinDLL("setupapi", use_last_error=True)
    api.SetupDiGetClassDevsW.restype = ctypes.c_void_p
    api.SetupDiGetClassDevsW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p,
                                         ctypes.c_void_p, ctypes.c_uint32]
    api.SetupDiEnumDeviceInfo.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p]
    api.SetupDiGetDeviceInstanceIdW.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                                ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_void_p]
    api.SetupDiGetDeviceRegistryPropertyW.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                                      ctypes.c_uint32, ctypes.c_void_p,
                                                      ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p]
    api.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]

    hset = api.SetupDiGetClassDevsW(None, None, None, DIGCF_PRESENT | DIGCF_ALLCLASS)
    if not hset or hset == INVALID_HANDLE:
        return []

    def _prop(d, prop) -> str:
        buf = ctypes.create_string_buffer(8192)
        req = ctypes.c_uint32(0); pt = ctypes.c_uint32(0)
        if api.SetupDiGetDeviceRegistryPropertyW(hset, byref(d), prop, byref(pt), buf, len(buf), byref(req)):
            sz = min(req.value, len(buf)) // 2
            try:
                return ctypes.wstring_at(buf, sz).rstrip("\x00")
            except Exception:
                return ""
        return ""

    devices: list[DeviceInfo] = []
    seen: set[str] = set()
    idx = 0
    try:
        while True:
            data = _SPDD(); data.cbSize = ctypes.sizeof(_SPDD)
            if not api.SetupDiEnumDeviceInfo(hset, idx, byref(data)):
                break
            idx += 1
            buf = create_unicode_buffer(1024); req = ctypes.c_int(0)
            api.SetupDiGetDeviceInstanceIdW(hset, byref(data), buf, len(buf), byref(req))
            iid  = buf.value
            hwid = _prop(data, SPDRP_HWID)
            vp   = VidPid.try_parse(iid + "\x00" + hwid)
            if vp is None or vp.compact in seen:
                continue
            cls  = _prop(data, SPDRP_CLASS)
            # FriendlyName is often empty for HID collections; fall back to the device
            # description ("MOZA Windows Driver") before the raw instance id.
            name = _prop(data, SPDRP_FRIENDLY) or _prop(data, SPDRP_DEVICEDESC) or iid
            mfg  = _prop(data, SPDRP_MFG)
            if not _is_controller(name, cls, hwid, iid):
                continue
            seen.add(vp.compact)
            devices.append(DeviceInfo(name=name.strip(), vid_pid=vp, instance_id=iid,
                                      class_name=cls, manufacturer=mfg.strip()))
    finally:
        api.SetupDiDestroyDeviceInfoList(hset)

    return sorted(devices, key=lambda d: d.name.lower())


_CTRL_SIGS = ["wheel", "wheelbase", "pedal", "shifter", "handbrake", "hand brake",
              "joystick", "gamepad", "game controller", "xbox", "dualshock", "dualsense",
              "simagic", "fanatec", "moza", "simucube", "thrustmaster", "logitech g",
              "ig_", "hid_device_system_game", "hid_device_system_joystick"]
_CTRL_EXCL = ["keyboard", "mouse", "touchpad", "webcam", "camera", "microphone",
              "audio", "headset", "rgb", "hub", "root hub", "monitor", "printer"]


def _is_controller(name: str, cls: str, hwid: str, iid: str) -> bool:
    if cls.lower() == "usb":
        return False
    hay = " ".join([name, cls, hwid, iid]).lower()
    if not any(s in hay for s in _CTRL_SIGS):
        return False
    if any(e in hay for e in _CTRL_EXCL):
        return "game controller" in hay or "hid_device_system_game" in hay
    return True
