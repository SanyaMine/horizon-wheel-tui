"""Persist and restore a WizardState as JSON so re-running / re-installing is instant.

Devices are stored by compact VID/PID + name + instance id, and re-resolved against the
live device list on load (falling back to a reconstructed DeviceInfo if the device is
absent, so paths and bindings remain usable).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from .devices import DeviceInfo
from .install import WizardState
from .profile import MappedInput, ProfileOptions
from .vidpid import VidPid

_VERSION = 1


def preset_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "HorizonWheelWizard" / "preset.json"


# ── Save ─────────────────────────────────────────────────────────────────────────────
def save_preset(state: WizardState, path: Optional[Path] = None) -> Path:
    p = path or preset_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "version": _VERSION,
        "roles": {r: _dev_to_dict(getattr(state, r))
                  for r in ("wheelbase", "pedals", "shifter", "handbrake")},
        "media_folder": state.media_folder,
        "input_zip": state.input_zip,
        "wheel_zip": state.wheel_zip,
        "output_folder": state.output_folder,
        "profile_name": state.profile_name,
        "ffb_template_entry": state.ffb_template_entry,
        "mode": state.mode,
        "base_profile_entry": state.base_profile_entry,
        "profile_options": _opts_to_dict(state.profile_options),
        "silenced_ids": list(state.silenced_ids),
        "bindings": {k: _mapped_to_dict(v) for k, v in state.bindings.items()},
    }
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return p


# ── Load ─────────────────────────────────────────────────────────────────────────────
def load_preset(path: Optional[Path] = None,
                devices: Optional[list[DeviceInfo]] = None) -> WizardState:
    p = path or preset_path()
    data = json.loads(p.read_text(encoding="utf-8"))
    by_compact = {d.vid_pid.compact: d for d in (devices or [])}

    state = WizardState(
        media_folder=data.get("media_folder", ""),
        input_zip=data.get("input_zip", ""),
        wheel_zip=data.get("wheel_zip", ""),
        output_folder=data.get("output_folder", ""),
        profile_name=data.get("profile_name", ""),
        ffb_template_entry=data.get("ffb_template_entry", ""),
        mode=data.get("mode", "capture"),
        base_profile_entry=data.get("base_profile_entry", ""),
        profile_options=_opts_from_dict(data.get("profile_options")),
        silenced_ids=list(data.get("silenced_ids", [])),
    )
    roles = data.get("roles", {})
    for r in ("wheelbase", "pedals", "shifter", "handbrake"):
        setattr(state, r, _dev_from_dict(roles.get(r), by_compact))
    state.bindings = {k: _mapped_from_dict(v) for k, v in data.get("bindings", {}).items()}
    return state


def has_preset(path: Optional[Path] = None) -> bool:
    return (path or preset_path()).exists()


# ── (de)serialization helpers ──────────────────────────────────────────────────────────
def _dev_to_dict(d: Optional[DeviceInfo]) -> Optional[dict]:
    if d is None:
        return None
    return {"compact": d.vid_pid.compact, "name": d.name, "instance_id": d.instance_id}


def _dev_from_dict(d: Optional[dict], by_compact: dict[str, DeviceInfo]) -> Optional[DeviceInfo]:
    if not d:
        return None
    compact = d.get("compact", "")
    live = by_compact.get(compact)
    if live is not None:
        return live
    if len(compact) == 8:
        return DeviceInfo(name=d.get("name", ""), vid_pid=VidPid(compact[:4], compact[4:]),
                          instance_id=d.get("instance_id", ""))
    return None


def _mapped_to_dict(m: MappedInput) -> dict:
    return {"input_type": m.input_type, "index": m.index, "invert_axis": m.invert_axis,
            "switch_position": m.switch_position, "device_vidpid": m.device_vidpid}


def _mapped_from_dict(d: dict) -> MappedInput:
    return MappedInput(input_type=d["input_type"], index=int(d["index"]),
                       invert_axis=bool(d.get("invert_axis", False)),
                       switch_position=d.get("switch_position"),
                       device_vidpid=d.get("device_vidpid", ""))


def _opts_to_dict(o: Optional[ProfileOptions]) -> Optional[dict]:
    if o is None:
        return None
    return {"steer_deadzones_around_center": o.steer_deadzones_around_center,
            "steer_inner_deadzone": o.steer_inner_deadzone,
            "steer_outer_deadzone": o.steer_outer_deadzone,
            "pedal_inner_deadzone": o.pedal_inner_deadzone,
            "pedal_outer_deadzone": o.pedal_outer_deadzone,
            "is_default_profile": o.is_default_profile,
            "profile_id": o.profile_id,
            "wider_mappings": o.wider_mappings}


def _opts_from_dict(d: Optional[dict]) -> Optional[ProfileOptions]:
    if not d:
        return None
    return ProfileOptions(
        steer_deadzones_around_center=bool(d.get("steer_deadzones_around_center", False)),
        steer_inner_deadzone=d.get("steer_inner_deadzone", "0.0"),
        steer_outer_deadzone=d.get("steer_outer_deadzone", "1.0"),
        pedal_inner_deadzone=d.get("pedal_inner_deadzone", "0.0"),
        pedal_outer_deadzone=d.get("pedal_outer_deadzone", "1.0"),
        is_default_profile=bool(d.get("is_default_profile", False)),
        profile_id=d.get("profile_id"),
        wider_mappings=bool(d.get("wider_mappings", False)))
