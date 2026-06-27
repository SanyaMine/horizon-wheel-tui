"""Wizard state + the generate→pack→verify→backup→install pipeline."""
from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional
from xml.etree import ElementTree as ET

from . import ffb, pack, quickmode
from .devices import DeviceInfo
from .forza import INPUT_ZIP, WHEEL_ZIP, read_ffb_ini
from .profile import (
    MappedInput, ProfileOptions, WheelMapResult, build_profile_xml, suggest_profile_name,
)
from .vidpid import VidPid


@dataclass
class WizardState:
    # Step 1 — device roles
    wheelbase: Optional[DeviceInfo] = None
    pedals:    Optional[DeviceInfo] = None
    shifter:   Optional[DeviceInfo] = None
    handbrake: Optional[DeviceInfo] = None

    # Step 2 — paths
    media_folder:  str = ""
    input_zip:     str = ""
    wheel_zip:     str = ""
    output_folder: str = ""

    # Step 3 — captured bindings: logical key -> MappedInput (device_vidpid pre-resolved)
    bindings: dict[str, MappedInput] = field(default_factory=dict)
    profile_name: str = ""

    # Step 4 — chosen FFB template entry
    ffb_template_entry: str = ""

    # Generation mode + options
    mode: str = "capture"                 # "capture" | "quick"
    base_profile_entry: str = ""          # quick-mode clone source / smarter-FFB base model
    profile_options: Optional[ProfileOptions] = None

    # Device silencing (instance ids the user chose to disable); applied via hwt.silence
    silenced_ids: list[str] = field(default_factory=list)

    def wheelbase_vidpid(self) -> VidPid:
        if self.wheelbase:
            return self.wheelbase.vid_pid
        return VidPid("0000", "0000")

    def role_for_joystick(self, joystick_name: str) -> Optional[DeviceInfo]:
        """Best-effort match of a captured pygame joystick name to a selected role."""
        jn = (joystick_name or "").lower()
        if not jn:
            return self.wheelbase
        for role in (self.pedals, self.shifter, self.handbrake, self.wheelbase):
            if role and role.name and role.name.lower()[:10] in jn:
                return role
        return self.wheelbase


def generate_and_install(state: WizardState, log: Callable[[str], None]) -> Path:
    out = Path(state.output_folder)
    out.mkdir(parents=True, exist_ok=True)

    vidpid = state.wheelbase_vidpid()
    device_name = state.wheelbase.name if state.wheelbase else "My Wheel"
    name = state.profile_name or suggest_profile_name(device_name)
    profile_name = _xml_name(name)

    if state.mode == "quick":
        if not state.base_profile_entry:
            raise ValueError("Quick mode needs a base wheel model to clone.")
        log(f"Cloning base profile {state.base_profile_entry} → {profile_name}…")
        base_xml = quickmode.read_profile_xml(state.input_zip, state.base_profile_entry)
        is_default = bool(state.profile_options and state.profile_options.is_default_profile)
        pinned_id = state.profile_options.profile_id if state.profile_options else None
        xml_bytes = quickmode.clone_profile_xml(base_xml, vidpid, name,
                                                is_default_profile=is_default, profile_id=pinned_id)
    else:
        log(f"Generating profile XML ({profile_name})…")
        result = WheelMapResult(device_vidpid=vidpid, device_name=device_name,
                                profile_name=name, inputs=dict(state.bindings))
        xml_bytes = build_profile_xml(result, state.profile_options)
    (out / profile_name).write_bytes(xml_bytes)

    ini_name = ffb.output_ini_name(vidpid)
    log(f"Patching FFB template → {ini_name}…")
    ini_text = read_ffb_ini(state.wheel_zip, state.ffb_template_entry)
    ini_text = ffb.set_vendor_product(ini_text, vidpid)
    (out / ini_name).write_text(ini_text, encoding="utf-8")

    out_input = out / INPUT_ZIP
    out_wheel = out / WHEEL_ZIP

    log(f"Building {INPUT_ZIP} (profile added alongside stock defaults)…")
    pack.write_input_zip(Path(state.input_zip), out_input, profile_name, xml_bytes)
    log(f"Building {WHEEL_ZIP}…")
    pack.write_wheel_zip(Path(state.wheel_zip), out_wheel, ini_name, ini_text)

    log("Verifying generated ZIPs (store-only, flat)…")
    for z in (out_input, out_wheel):
        ok, bad = pack.verify_store_only_top_level(z)
        if not ok:
            raise RuntimeError(f"ZIP verification failed for {z.name}: {bad[:3]} …")

    log("Backing up originals → HST-BACKUP and installing…")
    bf = pack.install_zips(state.media_folder, out_input, out_wheel)

    log("Post-install self-check (profile present, IsDefaultProfile, 0x VidPids)…")
    expect_default = bool(state.profile_options and state.profile_options.is_default_profile)
    ok, problems = verify_installed_profile(state.media_folder, profile_name, expect_default)
    if not ok:
        raise RuntimeError("Post-install check failed: " + "; ".join(problems))
    log("✔  Self-check passed.")
    log(f"Installed. Backup at: {bf}")
    return bf


def verify_installed_profile(media_folder: str | Path, profile_name: str,
                             expect_default: bool) -> tuple[bool, list[str]]:
    """Re-open the INSTALLED input zip and confirm our profile actually landed correctly:
    present under its flat entry name, `IsDefaultProfile` as requested, and EVERY per-`Value`
    `VidPid` carrying the mandatory `0x` prefix (the two bugs that silently broke binding).
    Returns (ok, problems)."""
    problems: list[str] = []
    entry = pack._top(profile_name)
    zip_path = Path(media_folder) / INPUT_ZIP
    try:
        with zipfile.ZipFile(zip_path) as z:
            names = {n.lower() for n in z.namelist()}
            if entry.lower() not in names:
                return False, [f"profile entry '{entry}' not found in {INPUT_ZIP}"]
            root = ET.fromstring(z.read(entry))
    except Exception as exc:
        return False, [f"could not read installed profile: {exc}"]

    prof = root[0] if root.tag == "Profiles" and len(root) else root
    if expect_default and prof.get("IsDefaultProfile") != "1":
        problems.append(f"IsDefaultProfile is {prof.get('IsDefaultProfile')!r}, expected '1'")
    if not (prof.get("PrimaryDeviceVidPid") or "").lower().startswith("0x"):
        problems.append("header PrimaryDeviceVidPid lacks 0x prefix")

    bad_vidpids = 0
    for el in root.iter():
        for name, val in el.attrib.items():
            if name.lower() == "vidpid" and not val.lower().startswith("0x"):
                bad_vidpids += 1
    if bad_vidpids:
        problems.append(f"{bad_vidpids} per-Value VidPid(s) missing the 0x prefix")
    return (not problems, problems)


def _xml_name(name: str) -> str:
    name = name.strip() or "DefaultRawGameControllerMappingProfileCustom"
    return name if name.lower().endswith(".xml") else name + ".xml"
