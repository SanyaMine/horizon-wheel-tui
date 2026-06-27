"""Quick mode: clone a shipped default profile and re-VID/PID it to the user's wheel.

Faithful port of the C# `XmlProfileEditor` "patch / generate from existing profile" path
(Program.cs:1387-1483). For a *supported* wheel this produces a complete, game-valid
profile instantly with no 26-step capture: take a shipped
`Default…RawGameControllerMappingProfile….xml`, rewrite every VID/PID attribute to the
wheel, set Primary/FFB, and (unless patching in place) assign a fresh Id.
"""
from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

from .vidpid import VidPid

_PROFILE_TAG = "RawGameControllerInputMappingProfile"


@dataclass
class BaseProfile:
    entry: str                 # zip entry name
    user_facing_name: str
    primary_vidpid: str        # compact, may be "" if unparseable


def list_profiles(input_zip: str | Path) -> list[BaseProfile]:
    """Shipped RawGameController profiles that can be cloned (have a PrimaryDeviceVidPid)."""
    out: list[BaseProfile] = []
    with zipfile.ZipFile(input_zip) as zf:
        for info in zf.infolist():
            if not info.filename.lower().endswith(".xml"):
                continue
            try:
                root = ET.fromstring(zf.read(info.filename))
            except Exception:
                continue
            prof = _find_profile(root)
            if prof is None:
                continue
            vp = VidPid.try_parse(prof.get("PrimaryDeviceVidPid"))
            out.append(BaseProfile(
                entry=info.filename,
                user_facing_name=prof.get("UserFacingName", info.filename),
                primary_vidpid=vp.compact if vp else "",
            ))
    out.sort(key=lambda b: b.entry.lower())
    return out


def read_profile_xml(input_zip: str | Path, entry: str) -> bytes:
    with zipfile.ZipFile(input_zip) as zf:
        return zf.read(entry)


def clone_profile_xml(base_xml: bytes, wheel: VidPid, profile_name: str,
                      patch_in_place: bool = False, is_default_profile: bool = False,
                      profile_id: str | None = None) -> bytes:
    """Clone a base profile, remapping every VID/PID to `wheel`.

    Unless `patch_in_place`, the clone gets a fresh Id; by default that id is STABLE
    (derived from the wheel's VID/PID via `profile.stable_profile_id`) so re-installs
    overwrite the same profile. Pass `profile_id` to pin a specific GUID (presets)."""
    root = ET.fromstring(base_xml)
    prof = _find_profile(root)
    if prof is None:
        raise ValueError("Base XML has no RawGameControllerInputMappingProfile element.")

    target = wheel.to_xml_string()
    # ApplyVidPidReplacements: every VidPid-bearing attribute → the wheel
    for el in root.iter():
        for name in list(el.attrib):
            if _is_vidpid_attr(name) and VidPid.try_parse(el.attrib[name]) is not None:
                el.set(name, target)

    _set_primary_and_ffb(prof, wheel)
    prof.set("UserFacingName", profile_name)
    prof.set("IsDefaultProfile", "1" if is_default_profile else "0")
    if not patch_in_place:
        from .profile import stable_profile_id
        prof.set("Id", (profile_id or stable_profile_id(wheel)).upper())

    ET.indent(root, space="  ")
    body = ET.tostring(root, encoding="unicode")
    return ('<?xml version="1.0" encoding="utf-8"?>\n' + body + "\n").encode("utf-8")


# ── helpers ──────────────────────────────────────────────────────────────────────────
def _find_profile(root: ET.Element) -> ET.Element | None:
    if _localname(root.tag) == _PROFILE_TAG:
        return root
    for el in root.iter():
        if _localname(el.tag) == _PROFILE_TAG:
            return el
    return None


def _localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]  # strip any namespace


def _is_vidpid_attr(name: str) -> bool:
    n = _localname(name)
    return n.lower() == "vidpid" or n.lower().endswith("vidpid")


def _set_primary_and_ffb(prof: ET.Element, wheel: VidPid) -> None:
    """Mirror C# SetPrimaryAndFfb (Program.cs:1453-1478)."""
    t = wheel.to_xml_string()
    prof.set("PrimaryDeviceVidPid", t)
    has_ffb_device = prof.get("FFBDeviceVidPid") is not None
    has_ffb = prof.get("FFBVidPid") is not None
    if has_ffb_device:
        prof.set("FFBDeviceVidPid", t)
    if has_ffb:
        prof.set("FFBVidPid", t)
    if not has_ffb_device and not has_ffb:
        prof.set("FFBDeviceVidPid", t)
    if prof.get("FFBMotorIndex") is None:
        prof.set("FFBMotorIndex", "0")
