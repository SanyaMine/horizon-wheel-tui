"""Enable/disable HID devices so Forza doesn't bind a phantom/duplicate controller.

Faithful port of the C# `DeviceSilencer` (Program.cs:1114-1234) using cfgmgr32 via ctypes.
All mutating operations require elevation (admin); callers should check `is_elevated()`
first and offer `relaunch_as_admin()`. Silenced instance ids are persisted so they can be
restored later.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterable

_CR_SUCCESS = 0x00000000
_CM_LOCATE_NORMAL = 0x00000000
_CM_LOCATE_PHANTOM = 0x00000001
_CM_PROB_DISABLED = 0x00000016

STATUS_ENABLED = "enabled"
STATUS_DISABLED = "disabled"
STATUS_UNKNOWN = "unknown"


def state_file_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "HorizonWheelWizard" / "silenced-devices.txt"


# ── Persistence ──────────────────────────────────────────────────────────────────────
def load_silenced_ids() -> list[str]:
    p = state_file_path()
    if not p.exists():
        return []
    out, lower = [], set()
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = line.strip()
        if s and s.lower() not in lower:
            lower.add(s.lower())
            out.append(s)
    return out


def save_silenced_ids(instance_ids: Iterable[str]) -> None:
    p = state_file_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    out, lower = [], set()
    for i in instance_ids:
        i = (i or "").strip()
        if i and i.lower() not in lower:
            lower.add(i.lower())
            out.append(i)
    p.write_text("\n".join(out), encoding="utf-8")


def clear_silenced_ids() -> None:
    p = state_file_path()
    if p.exists():
        p.unlink()


# ── Elevation ────────────────────────────────────────────────────────────────────────
def is_elevated() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin(args: list[str] | None = None) -> bool:
    """Best-effort UAC relaunch of this program elevated. Returns True if launched."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        params = " ".join(f'"{a}"' for a in (args or [sys.argv[0], *sys.argv[1:]]))
        rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
        return int(rc) > 32
    except Exception:
        return False


# ── cfgmgr32 device control ──────────────────────────────────────────────────────────
def _cfg():
    import ctypes
    cfg = ctypes.WinDLL("cfgmgr32")
    DEVINST = ctypes.c_uint32
    cfg.CM_Locate_DevNodeW.argtypes = [ctypes.POINTER(DEVINST), ctypes.c_wchar_p, ctypes.c_uint32]
    cfg.CM_Locate_DevNodeW.restype = ctypes.c_uint32
    cfg.CM_Disable_DevNode.argtypes = [DEVINST, ctypes.c_uint32]
    cfg.CM_Disable_DevNode.restype = ctypes.c_uint32
    cfg.CM_Enable_DevNode.argtypes = [DEVINST, ctypes.c_uint32]
    cfg.CM_Enable_DevNode.restype = ctypes.c_uint32
    cfg.CM_Get_DevNode_Status.argtypes = [ctypes.POINTER(ctypes.c_uint32),
                                          ctypes.POINTER(ctypes.c_uint32),
                                          DEVINST, ctypes.c_uint32]
    cfg.CM_Get_DevNode_Status.restype = ctypes.c_uint32
    return cfg, DEVINST


def _locate(cfg, DEVINST, instance_id: str) -> int:
    import ctypes
    dev = DEVINST(0)
    for flags in (_CM_LOCATE_NORMAL, _CM_LOCATE_PHANTOM):
        if cfg.CM_Locate_DevNodeW(ctypes.byref(dev), instance_id, flags) == _CR_SUCCESS:
            return dev.value
    raise RuntimeError(f"Could not find device {instance_id}.")


def get_status(instance_id: str) -> str:
    if sys.platform != "win32":
        return STATUS_UNKNOWN
    try:
        import ctypes
        cfg, DEVINST = _cfg()
        dev = _locate(cfg, DEVINST, instance_id)
        status = ctypes.c_uint32(0)
        problem = ctypes.c_uint32(0)
        if cfg.CM_Get_DevNode_Status(ctypes.byref(status), ctypes.byref(problem),
                                     DEVINST(dev), 0) != _CR_SUCCESS:
            return STATUS_UNKNOWN
        return STATUS_DISABLED if problem.value == _CM_PROB_DISABLED else STATUS_ENABLED
    except Exception:
        return STATUS_UNKNOWN


def disable_device(instance_id: str) -> None:
    cfg, DEVINST = _cfg()
    dev = _locate(cfg, DEVINST, instance_id)
    rc = cfg.CM_Disable_DevNode(DEVINST(dev), 0)
    if rc != _CR_SUCCESS:
        raise RuntimeError(f"Could not disable {instance_id} (cfgmgr32 0x{rc:X}). Run as admin.")


def enable_device(instance_id: str) -> None:
    cfg, DEVINST = _cfg()
    dev = _locate(cfg, DEVINST, instance_id)
    rc = cfg.CM_Enable_DevNode(DEVINST(dev), 0)
    if rc != _CR_SUCCESS:
        raise RuntimeError(f"Could not enable {instance_id} (cfgmgr32 0x{rc:X}). Run as admin.")
