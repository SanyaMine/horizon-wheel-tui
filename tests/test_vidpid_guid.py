"""SDL-GUID VID/PID parsing + the multi-device attribution regression (issue #1).

`VidPid.from_sdl_guid` is the fix for a two-device rig whose second controller's inputs were
being mis-attributed to the wheelbase: capture now reads each input's real VID/PID from the
pygame joystick GUID instead of fuzzy-matching SDL names to SetupAPI names.
"""
from xml.etree import ElementTree as ET

from hwt.profile import MappedInput, WheelMapResult, build_profile_xml
from hwt.vidpid import VidPid

# Real SDL GUID layout: vendor little-endian at hex 8:12, product little-endian at 16:20.
MS_PAD   = "030000005e0400008e02000010010000"  # Xbox pad -> vendor 045E, product 028E
SIMAGIC  = "03000000703600000005000010010000"  # -> vendor 3670, product 0500


def test_from_sdl_guid_extracts_vendor_product():
    assert VidPid.from_sdl_guid(MS_PAD).compact == "045E028E"
    assert VidPid.from_sdl_guid(SIMAGIC).compact == "36700500"


def test_from_sdl_guid_rejects_unusable():
    assert VidPid.from_sdl_guid("03000000000000000000000010010000") is None  # no VID/PID
    assert VidPid.from_sdl_guid("abc") is None                                # too short
    assert VidPid.from_sdl_guid("03000000zz0400008e02000010010000") is None   # non-hex
    assert VidPid.from_sdl_guid(None) is None
    assert VidPid.from_sdl_guid("") is None


def _find(prof, ctx_name, key):
    for c in prof:
        if c.tag == "Context" and c.get("Context") == ctx_name:
            for v in c.iter("Value"):
                if v.get("Key") == key:
                    return v
    return None


def test_second_device_binding_keeps_its_own_vidpid():
    """A binding captured on a second device must carry THAT device's VID/PID, not the
    wheelbase header's — the exact failure in the reported profile where every Value was the
    wheelbase (issue #1)."""
    wheelbase = VidPid("3670", "0500")
    hub = "36700501"  # different PID: a second Simagic device (button hub)
    r = WheelMapResult(device_vidpid=wheelbase, device_name="Simagic Evo Sport",
                       profile_name="Two Device Test")
    r.inputs["STEER"] = MappedInput("Axis", 0, device_vidpid=wheelbase.compact)
    r.inputs["CONFIRM"] = MappedInput("Button", 3, device_vidpid=hub)

    prof = ET.fromstring(build_profile_xml(r))[0]
    assert prof.get("PrimaryDeviceVidPid") == "0x36700500"  # header stays the wheelbase
    steer = _find(prof, "INPUTCONTEXT_RACING", "INPUTCMD_STEERING")
    confirm = _find(prof, "INPUTCONTEXT_RACING", "INPUTCMD_ACTIVATE")
    assert steer.get("VidPid") == "0x36700500"   # wheelbase axis
    assert confirm.get("VidPid") == "0x36700501"  # second device keeps its own VID/PID


def test_empty_device_vidpid_falls_back_to_header():
    """Preserve the historical fallback: an unresolved device_vidpid uses the header VID/PID."""
    r = WheelMapResult(device_vidpid=VidPid("3670", "0500"), profile_name="Fallback")
    r.inputs["CONFIRM"] = MappedInput("Button", 3, device_vidpid="")
    prof = ET.fromstring(build_profile_xml(r))[0]
    assert _find(prof, "INPUTCONTEXT_RACING", "INPUTCMD_ACTIVATE").get("VidPid") == "0x36700500"
