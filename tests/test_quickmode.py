from pathlib import Path
from xml.etree import ElementTree as ET

from hwt import quickmode
from hwt.vidpid import VidPid

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "inputmappingprofiles.zip"
WHEEL = VidPid("346E", "0015")
G29_ENTRY = "DefaultRawGameControllerMappingProfileLogitechG29.xml"


def test_list_profiles_includes_named_wheels():
    profiles = quickmode.list_profiles(INPUT)
    entries = {p.entry for p in profiles}
    assert G29_ENTRY in entries
    g29 = next(p for p in profiles if p.entry == G29_ENTRY)
    assert g29.primary_vidpid == "046DC24F"
    assert "G29" in g29.user_facing_name or g29.user_facing_name


def test_clone_remaps_all_vidpids():
    base = quickmode.read_profile_xml(INPUT, G29_ENTRY)
    out = quickmode.clone_profile_xml(base, WHEEL, "MyMozaClone")
    root = ET.fromstring(out)
    prof = root[0] if root.tag == "Profiles" else root

    # every VidPid-bearing attribute now points at the wheel
    target = WHEEL.to_xml_string()
    for el in root.iter():
        for name, val in el.attrib.items():
            if name.lower() == "vidpid" or name.lower().endswith("vidpid"):
                assert val == target, f"{name}={val}"

    assert prof.get("PrimaryDeviceVidPid") == target
    assert prof.get("FFBDeviceVidPid") == target
    assert prof.get("UserFacingName") == "MyMozaClone"
    assert prof.get("IsDefaultProfile") == "0"
    # new Id assigned (different from the shipped G29 id) and uppercase
    assert prof.get("Id") and prof.get("Id") != "cc531261-45f8-4552-9a7c-e527b3de90a9"


def test_clone_patch_in_place_keeps_id():
    base = quickmode.read_profile_xml(INPUT, G29_ENTRY)
    orig_id = ET.fromstring(base)[0].get("Id")
    out = quickmode.clone_profile_xml(base, WHEEL, "Keep", patch_in_place=True)
    assert ET.fromstring(out)[0].get("Id") == orig_id
