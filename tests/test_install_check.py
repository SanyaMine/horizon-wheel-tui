"""Tests for the post-install self-check (install.verify_installed_profile)."""
from pathlib import Path

from hwt import pack
from hwt.install import verify_installed_profile
from hwt.profile import ProfileOptions, build_profile_xml
from tests.fixtures import full_capture_result

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "inputmappingprofiles.zip"
ENTRY = "DefaultRawGameControllerMappingProfileMOZACustom.xml"


def _install(media: Path, xml: bytes) -> None:
    media.mkdir(exist_ok=True)
    dst = media / "inputmappingprofiles.zip"
    pack.write_input_zip(INPUT, dst, ENTRY, xml)


def test_check_passes_on_good_profile(tmp_path):
    media = tmp_path / "media"
    xml = build_profile_xml(full_capture_result(), ProfileOptions(is_default_profile=True))
    _install(media, xml)
    ok, problems = verify_installed_profile(media, ENTRY, expect_default=True)
    assert ok, problems


def test_check_flags_missing_default(tmp_path):
    media = tmp_path / "media"
    xml = build_profile_xml(full_capture_result())  # IsDefaultProfile="0"
    _install(media, xml)
    ok, problems = verify_installed_profile(media, ENTRY, expect_default=True)
    assert not ok
    assert any("IsDefaultProfile" in p for p in problems)


def test_check_flags_missing_0x_vidpid(tmp_path):
    media = tmp_path / "media"
    xml = build_profile_xml(full_capture_result(), ProfileOptions(is_default_profile=True))
    xml = xml.replace(b'VidPid="0x346E0015"', b'VidPid="346E0015"')  # strip the prefix
    _install(media, xml)
    ok, problems = verify_installed_profile(media, ENTRY, expect_default=True)
    assert not ok
    assert any("0x prefix" in p for p in problems)


def test_check_flags_absent_profile(tmp_path):
    media = tmp_path / "media"
    xml = build_profile_xml(full_capture_result())
    _install(media, xml)
    ok, problems = verify_installed_profile(media, "NotThere.xml", expect_default=False)
    assert not ok
    assert any("not found" in p for p in problems)
