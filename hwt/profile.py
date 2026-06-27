"""Build a Forza Horizon 6 RawGameController input-mapping profile from captured inputs.

This is the heart of the port — a 1:1 reimplementation of
`WheelMapWizard.BuildXmlDocument` and its ten `Build*Context` helpers
(WheelMapWizard.cs:487-729). The profile is built FROM SCRATCH out of the captured
logical inputs; each logical input fans out to many INPUTCMD_* keys across contexts.

Output is bytes of a `<Profiles>` document. Element/attribute names and ordering match
the C# output and the game's own shipped profiles (verified against
DefaultRawGameControllerMappingProfileLogitechG29.xml).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Optional
from xml.etree import ElementTree as ET

from .vidpid import VidPid


@dataclass
class MappedInput:
    """One captured physical input bound to a logical key.

    device_vidpid is the capturing device's raw "VVVVPPPP" (uppercase, no 0x), matching
    the C# `DeviceState.VidPid`. It becomes the per-<Value> VidPid attribute; when empty
    the profile's header VID/PID (0x form) is used as a fallback (WheelMapWizard.cs:745).
    """
    input_type: str                       # "Axis" | "Button" | "Switch"
    index: int
    invert_axis: bool = False
    switch_position: Optional[str] = None  # "Up"|"Down"|"Left"|"Right" for Switch
    device_vidpid: str = ""


@dataclass
class WheelMapResult:
    device_vidpid: VidPid
    device_name: str = ""
    profile_name: str = ""
    # logical key (e.g. "STEER") -> MappedInput
    inputs: dict[str, MappedInput] = field(default_factory=dict)


@dataclass
class ProfileOptions:
    """Optional, opt-in tuning applied to the RACING driving axes after the faithful
    build. With the default values (or options=None) the output is byte-identical to
    upstream — these only change things when explicitly enabled in the UI."""
    steer_deadzones_around_center: bool = False  # matches shipped wheel profiles
    steer_inner_deadzone: str = "0.0"
    steer_outer_deadzone: str = "1.0"
    pedal_inner_deadzone: str = "0.0"
    pedal_outer_deadzone: str = "1.0"
    # When True, header IsDefaultProfile="1" so Forza AUTO-APPLIES the profile to the
    # matching device (no manual selection). Required for wheels Forza doesn't natively
    # recognize (e.g. Moza R3) — otherwise the profile is available but never applied.
    is_default_profile: bool = False
    # Explicit profile Id (uppercase GUID). When None, build_profile_xml derives a STABLE
    # id from the wheel's VID/PID so re-installs overwrite the same profile in place rather
    # than spawning a fresh random one each run. Set this to pin a specific id (presets).
    profile_id: Optional[str] = None
    # When True, emit the extra coverage that shipped profiles have but the faithful 26-input
    # build omits: H-pattern gears (RACING), brake-as-left-trigger (UI), and the whole
    # PROP_PLACEMENT_UI context. Off by default → output byte-identical to the faithful build
    # (golden-file guarded). Gears only appear if their inputs were actually captured.
    wider_mappings: bool = False


# Namespace for deterministic profile ids — arbitrary fixed UUID so the mapping
# VID/PID → id is stable across runs and machines.
_PROFILE_ID_NS = uuid.UUID("6f1d7c2a-3b8e-4a51-9c0d-2e7f5a4b1c33")


def stable_profile_id(vidpid: VidPid) -> str:
    """Deterministic uppercase GUID derived from the wheel's VID/PID. The same wheel always
    yields the same id, so re-installing updates the existing profile instead of duplicating."""
    return str(uuid.uuid5(_PROFILE_ID_NS, "HorizonWheelWizard:" + vidpid.compact)).upper()


# ════════════════════════════════════════════════════════════════════════════════════
#  Public entry point
# ════════════════════════════════════════════════════════════════════════════════════
def build_profile_xml(result: WheelMapResult, options: "ProfileOptions | None" = None) -> bytes:
    vid = result.device_vidpid.to_xml_string()           # header form: 0x + UPPER
    profile_id = (options.profile_id if options and options.profile_id
                  else stable_profile_id(result.device_vidpid))

    profile = ET.Element("RawGameControllerInputMappingProfile", {
        "Version": "1",
        "Id": profile_id,
        "UserFacingName": result.profile_name or result.device_name or "My Wheel",
        "IsDefaultProfile": "1" if (options and options.is_default_profile) else "0",
        "PrimaryDeviceVidPid": vid,
        "FFBDeviceVidPid": vid,
        "FFBMotorIndex": "0",
    })

    m = result.inputs
    wider = bool(options and options.wider_mappings)

    racing = _build_racing(m, vid, wider)
    profile.append(ET.Comment(" Race "))
    profile.append(racing)
    profile.append(ET.Comment(" UI "))
    profile.append(_build_ui(m, vid, wider))
    profile.append(ET.Comment(" Racing UI overlays "))
    profile.append(_build_racing_ui(m, vid))
    profile.append(ET.Comment(" Anna menu "))
    profile.append(_build_anna(m, vid))
    profile.append(ET.Comment(" Drone / Copter "))
    profile.append(_build_copter(m, vid))
    profile.append(ET.Comment(" Race (restricted) "))
    profile.append(_build_racing_camera_only(m, vid))
    profile.append(ET.Comment(" Free camera "))
    profile.append(_build_freecam(m, vid))
    profile.append(ET.Comment(" Hide and Seek "))
    profile.append(_build_hide_seek(m, vid))
    profile.append(ET.Comment(" Eliminator "))
    profile.append(_build_eliminator(m, vid))
    profile.append(ET.Comment(" Car Meets "))
    profile.append(_build_car_meets(m, vid))
    if wider:
        profile.append(ET.Comment(" Prop Placement (EventLab) "))
        profile.append(_build_prop_placement(m, vid))

    if options is not None:
        _apply_profile_options(racing, options)

    root = ET.Element("Profiles")
    root.append(profile)
    ET.indent(root, space="  ")
    body = ET.tostring(root, encoding="unicode")
    return ('<?xml version="1.0" encoding="utf-8"?>\n' + body + "\n").encode("utf-8")


# ════════════════════════════════════════════════════════════════════════════════════
#  Element helpers (BuildValueElement / complex pairs)
# ════════════════════════════════════════════════════════════════════════════════════
def _ctx(name: str) -> ET.Element:
    return ET.Element("Context", {"Version": "1", "Context": name})


def _per_value_vidpid(raw: str) -> str:
    """Per-<Value> VidPid in the shipped game format: a `0x`-prefixed value (e.g.
    `0x346E0015`). The game requires the `0x` prefix to match the binding to the device —
    without it (the older, incorrect assumption) NONE of the bindings bind. Verified against
    the shipped `DefaultRawGameControllerMappingProfileLogitechG29.xml` (`VidPid="0x046dc24f"`)."""
    return raw if raw.lower().startswith("0x") else "0x" + raw


def _value(inp: MappedInput, key: str, vid: str,
           inner_dz: Optional[str] = None, outer_dz: Optional[str] = None) -> ET.Element:
    effective_vid = inp.device_vidpid if inp.device_vidpid else vid
    attrs = {
        "Version": "1",
        "Key": key,
        "VidPid": _per_value_vidpid(effective_vid),
        "InputType": inp.input_type,
        "Index": str(inp.index),
    }
    el = ET.Element("Value", attrs)
    if inp.input_type == "Axis":
        el.set("InvertAxis", "true" if inp.invert_axis else "false")
        el.set("InnerDeadzone", inner_dz if inner_dz is not None else "0.0")
        el.set("OuterDeadzone", outer_dz if outer_dz is not None else "1.0")
    elif inp.input_type == "Switch" and inp.switch_position:
        el.set("SwitchPosition", inp.switch_position)
    return el


def _add(ctx: ET.Element, m: dict[str, MappedInput], key: str, cmd: str, vid: str,
         inner_dz: Optional[str] = None, outer_dz: Optional[str] = None) -> None:
    """AddIfExists: emit a <Value> for logical `key` as INPUTCMD `cmd` if captured."""
    inp = m.get(key)
    if inp is None:
        return
    ctx.append(_value(inp, cmd, vid, inner_dz, outer_dz))


def _complex_axis_pair(cmd: str, low: MappedInput, high: Optional[MappedInput], vid: str) -> ET.Element:
    el = ET.Element("Value", {"Version": "1", "Key": cmd})
    el.append(_input_cmd("InputCmdLow", low, vid, axis_dz=True))
    if high is not None:
        el.append(_input_cmd("InputCmdHigh", high, vid, axis_dz=True))
    return el


def _complex_button_pair(cmd: str, low: MappedInput, high: MappedInput, vid: str) -> ET.Element:
    el = ET.Element("Value", {"Version": "1", "Key": cmd})
    el.append(_input_cmd("InputCmdLow", low, vid, axis_dz=False))
    el.append(_input_cmd("InputCmdHigh", high, vid, axis_dz=False))
    return el


def _input_cmd(tag: str, inp: MappedInput, vid: str, axis_dz: bool) -> ET.Element:
    effective_vid = inp.device_vidpid if inp.device_vidpid else vid
    el = ET.Element(tag, {
        "VidPid": _per_value_vidpid(effective_vid),
        "InputType": inp.input_type,
        "Index": str(inp.index),
    })
    if axis_dz:
        el.set("InvertAxis", "true" if inp.invert_axis else "false")
        el.set("InnerDeadzone", "0.05")
        el.set("OuterDeadzone", "0.95")
    elif inp.input_type == "Switch" and inp.switch_position:
        el.set("SwitchPosition", inp.switch_position)
    return el


# ════════════════════════════════════════════════════════════════════════════════════
#  The 10 context builders (mirror WheelMapWizard.cs:539-729)
# ════════════════════════════════════════════════════════════════════════════════════
def _build_racing(m: dict[str, MappedInput], vid: str, wider: bool = False) -> ET.Element:
    ctx = _ctx("INPUTCONTEXT_RACING")
    _add(ctx, m, "GAS",        "INPUTCMD_GAS",        vid)
    _add(ctx, m, "BRAKE",      "INPUTCMD_BRAKE",      vid)
    _add(ctx, m, "CLUTCH",     "INPUTCMD_CLUTCH",     vid)
    _add(ctx, m, "STEER",      "INPUTCMD_STEERING",   vid)
    _add(ctx, m, "SHIFT_UP",   "INPUTCMD_SHIFTUP",    vid)
    _add(ctx, m, "SHIFT_DOWN", "INPUTCMD_SHIFTDOWN",  vid)
    _add(ctx, m, "SHIFT_DOWN", "INPUTCMD_AUTODRIVE_CINEMATIC_CAMERA", vid)
    _add(ctx, m, "REWIND",     "INPUTCMD_MULLIGAN",   vid)
    _add(ctx, m, "HANDBRAKE",  "INPUTCMD_HANDBRAKE",  vid)
    _add(ctx, m, "PAUSE",      "INPUTCMD_PAUSE_GAME", vid)
    _add(ctx, m, "HORN",       "INPUTCMD_HORN",       vid)
    _add(ctx, m, "CONFIRM",    "INPUTCMD_ACTIVATE",   vid)
    _add(ctx, m, "CAMERA",     "INPUTCMD_SWITCH_CAMERA", vid)
    _add(ctx, m, "RADIO",      "INPUTCMD_RADIO_RIGHT",   vid)
    _add(ctx, m, "ANNA",       "INPUTCMD_ANNA_ACTIVATE", vid)
    _add(ctx, m, "TELEMETRY",  "INPUTCMD_TELEMETRY_TOGGLE", vid)
    _add(ctx, m, "NAV_LEFT",   "INPUTCMD_TELEMETRY_PREV",  vid)
    _add(ctx, m, "NAV_RIGHT",  "INPUTCMD_TELEMETRY_NEXT",  vid)
    _add(ctx, m, "MAP",        "INPUTCMD_OPEN_MAP",        vid)
    if wider:
        # H-pattern shifter gears (only emitted if the gear inputs were captured).
        _add(ctx, m, "GEAR_R", "INPUTCMD_GEAR_REVERSE", vid)
        _add(ctx, m, "GEAR_1", "INPUTCMD_GEAR_FIRST",   vid)
        _add(ctx, m, "GEAR_2", "INPUTCMD_GEAR_SECOND",  vid)
        _add(ctx, m, "GEAR_3", "INPUTCMD_GEAR_THIRD",   vid)
        _add(ctx, m, "GEAR_4", "INPUTCMD_GEAR_FOURTH",  vid)
        _add(ctx, m, "GEAR_5", "INPUTCMD_GEAR_FIFTH",   vid)
        _add(ctx, m, "GEAR_6", "INPUTCMD_GEAR_SIXTH",   vid)
        _add(ctx, m, "GEAR_7", "INPUTCMD_GEAR_SEVENTH", vid)
    return ctx


def _build_ui(m: dict[str, MappedInput], vid: str, wider: bool = False) -> ET.Element:
    ctx = _ctx("INPUTCONTEXT_UI")
    # D-Pad
    _add(ctx, m, "NAV_UP",    "INPUTCMD_UI_DPAD_UP_PRESS",    vid)
    _add(ctx, m, "NAV_DOWN",  "INPUTCMD_UI_DPAD_DOWN_PRESS",  vid)
    _add(ctx, m, "NAV_LEFT",  "INPUTCMD_UI_DPAD_LEFT_PRESS",  vid)
    _add(ctx, m, "NAV_RIGHT", "INPUTCMD_UI_DPAD_RIGHT_PRESS", vid)

    for cmd in ("INPUTCMD_UI_OK_PRESS", "INPUTCMD_UI_OK_RELEASE", "INPUTCMD_UI_OK_REPEAT", "INPUTCMD_UI_OK_WHILEDOWN"):
        _add(ctx, m, "CONFIRM", cmd, vid)
    for cmd in ("INPUTCMD_UI_CANCEL_PRESS", "INPUTCMD_UI_CANCEL_RELEASE", "INPUTCMD_UI_CANCEL_REPEAT", "INPUTCMD_UI_CANCEL_WHILEDOWN"):
        _add(ctx, m, "CANCEL", cmd, vid)
    for cmd in ("INPUTCMD_UI_START_PRESS", "INPUTCMD_UI_START_RELEASE", "INPUTCMD_UI_START_REPEAT"):
        _add(ctx, m, "PAUSE", cmd, vid)
    for cmd in ("INPUTCMD_UI_BACK_PRESS", "INPUTCMD_UI_BACK_RELEASE", "INPUTCMD_UI_BACK_REPEAT"):
        _add(ctx, m, "BACK", cmd, vid)

    for cmd in ("INPUTCMD_UI_UP_PRESS", "INPUTCMD_UI_UP_RELEASE", "INPUTCMD_UI_UP_REPEAT"):
        _add(ctx, m, "NAV_UP", cmd, vid)
    for cmd in ("INPUTCMD_UI_DOWN_PRESS", "INPUTCMD_UI_DOWN_RELEASE", "INPUTCMD_UI_DOWN_REPEAT"):
        _add(ctx, m, "NAV_DOWN", cmd, vid)
    for cmd in ("INPUTCMD_UI_LEFT_PRESS", "INPUTCMD_UI_LEFT_RELEASE", "INPUTCMD_UI_LEFT_REPEAT"):
        _add(ctx, m, "NAV_LEFT", cmd, vid)
    for cmd in ("INPUTCMD_UI_RIGHT_PRESS", "INPUTCMD_UI_RIGHT_RELEASE", "INPUTCMD_UI_RIGHT_REPEAT"):
        _add(ctx, m, "NAV_RIGHT", cmd, vid)

    # Right trigger (gas axis in menus)
    for cmd in ("INPUTCMD_UI_RTRIGGER_PRESS", "INPUTCMD_UI_RTRIGGER_RELEASE", "INPUTCMD_UI_RTRIGGER_REPEAT"):
        _add(ctx, m, "GAS", cmd, vid, inner_dz="0.05", outer_dz="0.95")
    if wider:
        # Left trigger (brake axis in menus) — mirror of the right trigger above.
        for cmd in ("INPUTCMD_UI_LTRIGGER_PRESS", "INPUTCMD_UI_LTRIGGER_RELEASE", "INPUTCMD_UI_LTRIGGER_REPEAT"):
            _add(ctx, m, "BRAKE", cmd, vid, inner_dz="0.05", outer_dz="0.95")

    # Bumpers (shift paddles in menus)
    for cmd in ("INPUTCMD_UI_LBUMPER_PRESS", "INPUTCMD_UI_LBUMPER_RELEASE", "INPUTCMD_UI_LBUMPER_REPEAT"):
        _add(ctx, m, "SHIFT_DOWN", cmd, vid)
    for cmd in ("INPUTCMD_UI_RBUMPER_PRESS", "INPUTCMD_UI_RBUMPER_RELEASE", "INPUTCMD_UI_RBUMPER_REPEAT"):
        _add(ctx, m, "SHIFT_UP", cmd, vid)
    _add(ctx, m, "SHIFT_DOWN", "INPUTCMD_PREV_CATEGORY", vid)
    _add(ctx, m, "SHIFT_UP",   "INPUTCMD_NEXT_CATEGORY", vid)

    # Brick challenges (DPad again)
    for key, cmd in (("NAV_UP", "INPUTCMD_UI_BRICKCHALLENGES_UP"),
                     ("NAV_DOWN", "INPUTCMD_UI_BRICKCHALLENGES_DOWN"),
                     ("NAV_LEFT", "INPUTCMD_UI_BRICKCHALLENGES_LEFT"),
                     ("NAV_RIGHT", "INPUTCMD_UI_BRICKCHALLENGES_RIGHT")):
        _add(ctx, m, key, cmd, vid)

    _add(ctx, m, "REWIND", "INPUTCMD_MULLIGAN", vid)

    # Map move (complex pairs)
    if "BRAKE" in m and "GAS" in m:
        ctx.append(_complex_axis_pair("INPUTCMD_UI_MAP_MOVE_LEFTRIGHT", m["BRAKE"], m["GAS"], vid))
        ctx.append(_complex_axis_pair("INPUTCMD_UI_REPLAY_SPEED_RIGHT", m["GAS"], None, vid))
        ctx.append(_complex_axis_pair("INPUTCMD_UI_REPLAY_SPEED_LEFT",  m["BRAKE"], None, vid))
    if "NAV_DOWN" in m and "NAV_UP" in m:
        ctx.append(_complex_button_pair("INPUTCMD_UI_MAP_MOVE_UPDOWN", m["NAV_DOWN"], m["NAV_UP"], vid))

    for cmd in ("INPUTCMD_UI_X_PRESS", "INPUTCMD_UI_X_RELEASE", "INPUTCMD_UI_X_REPEAT"):
        _add(ctx, m, "BTN_X", cmd, vid)
    for cmd in ("INPUTCMD_UI_Y_PRESS", "INPUTCMD_UI_Y_RELEASE", "INPUTCMD_UI_Y_REPEAT"):
        _add(ctx, m, "BTN_Y", cmd, vid)
    for cmd in ("INPUTCMD_UI_VIEW_PRESS", "INPUTCMD_UI_VIEW_RELEASE", "INPUTCMD_UI_VIEW_REPEAT"):
        _add(ctx, m, "MAP", cmd, vid)

    return ctx


def _build_racing_ui(m: dict[str, MappedInput], vid: str) -> ET.Element:
    ctx = _ctx("INPUTCONTEXT_RACING_UI")
    _add(ctx, m, "ANNA",      "INPUTCMD_ANNA_ACTIVATE",     vid)
    _add(ctx, m, "PHOTO",     "INPUTCMD_PHOTO_MODE_TOGGLE", vid)
    _add(ctx, m, "QUICKCHAT", "INPUTCMD_QUICKCHAT_ACTIVATE", vid)
    _add(ctx, m, "RADIO",     "INPUTCMD_RADIO_RIGHT",       vid)
    return ctx


def _build_anna(m: dict[str, MappedInput], vid: str) -> ET.Element:
    ctx = _ctx("INPUTCONTEXT_ANNA")
    _add(ctx, m, "NAV_UP",    "INPUTCMD_ANNA_ITEM_1", vid)
    _add(ctx, m, "NAV_LEFT",  "INPUTCMD_ANNA_ITEM_2", vid)
    _add(ctx, m, "NAV_RIGHT", "INPUTCMD_ANNA_ITEM_3", vid)
    _add(ctx, m, "NAV_DOWN",  "INPUTCMD_ANNA_ITEM_4", vid)
    return ctx


def _build_copter(m: dict[str, MappedInput], vid: str) -> ET.Element:
    ctx = _ctx("INPUTCONTEXT_COPTER")
    _add(ctx, m, "PHOTO",     "INPUTCMD_PHOTO_MODE_TOGGLE",  vid)
    _add(ctx, m, "QUICKCHAT", "INPUTCMD_QUICKCHAT_ACTIVATE", vid)
    _add(ctx, m, "RADIO",     "INPUTCMD_RADIO_RIGHT",        vid)
    return ctx


def _build_racing_camera_only(m: dict[str, MappedInput], vid: str) -> ET.Element:
    ctx = _ctx("INPUTCONTEXT_RACING_CAMERA_ONLY")
    _add(ctx, m, "PAUSE",     "INPUTCMD_PAUSE_GAME",      vid)
    _add(ctx, m, "CAMERA",    "INPUTCMD_SWITCH_CAMERA",   vid)
    _add(ctx, m, "HORN",      "INPUTCMD_HORN",            vid)
    _add(ctx, m, "CONFIRM",   "INPUTCMD_ACTIVATE",        vid)
    _add(ctx, m, "ANNA",      "INPUTCMD_ANNA_ACTIVATE",   vid)
    _add(ctx, m, "TELEMETRY", "INPUTCMD_TELEMETRY_TOGGLE", vid)
    _add(ctx, m, "NAV_LEFT",  "INPUTCMD_TELEMETRY_PREV",  vid)
    _add(ctx, m, "NAV_RIGHT", "INPUTCMD_TELEMETRY_NEXT",  vid)
    return ctx


def _build_freecam(m: dict[str, MappedInput], vid: str) -> ET.Element:
    ctx = _ctx("INPUTCONTEXT_FREECAM")
    if "BRAKE" in m and "GAS" in m:
        ctx.append(_complex_axis_pair("INPUTCMD_UI_MAP_MOVE_LEFTRIGHT", m["BRAKE"], m["GAS"], vid))
    return ctx


def _build_hide_seek(m: dict[str, MappedInput], vid: str) -> ET.Element:
    ctx = _ctx("INPUTCONTEXT_HIDE_SEEK")
    _add(ctx, m, "BTN_Y", "INPUTCMD_HIDESEEK_PING_OR_CHASEBREAK", vid)
    return ctx


def _build_eliminator(m: dict[str, MappedInput], vid: str) -> ET.Element:
    ctx = _ctx("INPUTCONTEXT_ELIMINATOR_UI")
    _add(ctx, m, "NAV_LEFT",  "INPUTCMD_ELIMINATOR_UPGRADECHOICE_LEFT",  vid)
    _add(ctx, m, "NAV_DOWN",  "INPUTCMD_ELIMINATOR_UPGRADECHOICE_DOWN",  vid)
    _add(ctx, m, "NAV_RIGHT", "INPUTCMD_ELIMINATOR_UPGRADECHOICE_RIGHT", vid)
    return ctx


def _build_car_meets(m: dict[str, MappedInput], vid: str) -> ET.Element:
    ctx = _ctx("INPUTCONTEXT_CAR_MEETS")
    _add(ctx, m, "NAV_LEFT", "INPUTCMD_QUICKCHAT_ACTIVATE",      vid)
    _add(ctx, m, "NAV_UP",   "INPUTCMD_CAR_MEETS_PHOTO",         vid)
    _add(ctx, m, "NAV_DOWN", "INPUTCMD_CAR_MEETS_CINEMATIC_CAM", vid)
    return ctx


def _build_prop_placement(m: dict[str, MappedInput], vid: str) -> ET.Element:
    """EventLab / Prop Placement editor. Not in upstream C# — built from already-captured
    logical inputs (d-pad transforms; face buttons / paddles / handbrake / camera / map for the
    rest), mapped semantically to the INPUTCMD_PP_* keys the shipped profiles use."""
    ctx = _ctx("INPUTCONTEXT_PROP_PLACEMENT_UI")
    # Move/rotate the selected prop with the d-pad.
    _add(ctx, m, "NAV_UP",    "INPUTCMD_PP_TRANSFORM_UP",    vid)
    _add(ctx, m, "NAV_DOWN",  "INPUTCMD_PP_TRANSFORM_DOWN",  vid)
    _add(ctx, m, "NAV_LEFT",  "INPUTCMD_PP_TRANSFORM_LEFT",  vid)
    _add(ctx, m, "NAV_RIGHT", "INPUTCMD_PP_TRANSFORM_RIGHT", vid)
    # Confirm-style: place / select.
    _add(ctx, m, "CONFIRM", "INPUTCMD_PP_PLACE_EDIT_PROP",   vid)
    _add(ctx, m, "CONFIRM", "INPUTCMD_PP_SPHERE_SELECTION",  vid)
    _add(ctx, m, "CONFIRM", "INPUTCMD_PP_ADD_TO_SELECTION",  vid)
    # Cancel-style: delete / remove.
    _add(ctx, m, "CANCEL",  "INPUTCMD_PP_DELETE_PROP",                vid)
    _add(ctx, m, "CANCEL",  "INPUTCMD_PP_DELETE_UGCPROP_IN_CAROUSEL", vid)
    _add(ctx, m, "CANCEL",  "INPUTCMD_PP_REMOVE_FROM_SELECTION",      vid)
    # Back: save & exit.
    _add(ctx, m, "BACK",    "INPUTCMD_PP_SAVE_AND_EXIT",     vid)
    # Y: clone / stamp / save selection.
    _add(ctx, m, "BTN_Y",   "INPUTCMD_PP_CLONE_PROP",        vid)
    _add(ctx, m, "BTN_Y",   "INPUTCMD_PP_STAMP_PROP",        vid)
    _add(ctx, m, "BTN_Y",   "INPUTCMD_PP_SAVE_SELECTED_PROPS", vid)
    # X: library / prefab / creation mode.
    _add(ctx, m, "BTN_X",   "INPUTCMD_PP_OPEN_LIBRARY",         vid)
    _add(ctx, m, "BTN_X",   "INPUTCMD_PP_OPEN_PROPPREFAB_POPUP", vid)
    _add(ctx, m, "BTN_X",   "INPUTCMD_PP_OPEN_CREATIONMODE",    vid)
    # Map/View: more-options / search / selection mode.
    _add(ctx, m, "MAP",     "INPUTCMD_PP_OPEN_MOREOPTIONS",          vid)
    _add(ctx, m, "MAP",     "INPUTCMD_PP_OPEN_PROPPREFAB_SEARCHPOPUP", vid)
    _add(ctx, m, "MAP",     "INPUTCMD_PP_OPEN_SELECTIONMODE",        vid)
    # Paddles: roll / undo / redo.
    _add(ctx, m, "SHIFT_DOWN", "INPUTCMD_PP_ROLL_LEFT",  vid)
    _add(ctx, m, "SHIFT_DOWN", "INPUTCMD_PP_UNDO",       vid)
    _add(ctx, m, "SHIFT_UP",   "INPUTCMD_PP_ROLL_RIGHT", vid)
    _add(ctx, m, "SHIFT_UP",   "INPUTCMD_PP_REDO",       vid)
    # Misc.
    _add(ctx, m, "HANDBRAKE", "INPUTCMD_PP_RESET_TRANSFORM", vid)
    _add(ctx, m, "CAMERA",    "INPUTCMD_PP_PRECISION_MODE",  vid)
    return ctx


def _apply_profile_options(racing: ET.Element, opts: ProfileOptions) -> None:
    """Apply opt-in tuning to the RACING driving axes (no-op for non-axis values)."""
    pedals = {"INPUTCMD_GAS", "INPUTCMD_BRAKE", "INPUTCMD_CLUTCH"}
    for v in racing.findall("Value"):
        if v.get("InputType") != "Axis":
            continue
        key = v.get("Key")
        if key == "INPUTCMD_STEERING":
            if opts.steer_deadzones_around_center:
                v.set("DeadzonesAroundCenter", "true")
            v.set("InnerDeadzone", opts.steer_inner_deadzone)
            v.set("OuterDeadzone", opts.steer_outer_deadzone)
        elif key in pedals:
            v.set("InnerDeadzone", opts.pedal_inner_deadzone)
            v.set("OuterDeadzone", opts.pedal_outer_deadzone)


def suggest_profile_name(device_name: str) -> str:
    """WheelMapWizard.cs:479-483 — sanitize device name into a default profile name."""
    safe = "".join(c if c.isalnum() else "_" for c in device_name).strip("_")
    return "DefaultRawGameControllerMappingProfile" + safe + "Custom"
