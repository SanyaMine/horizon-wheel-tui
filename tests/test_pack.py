import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from hwt import pack
from hwt.profile import build_profile_xml
from tests.fixtures import full_capture_result

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "inputmappingprofiles.zip"
WHEEL = ROOT / "wheeltunablesettingspc.zip"


def test_write_input_zip_roundtrip(tmp_path):
    xml = build_profile_xml(full_capture_result())
    dst = tmp_path / "inputmappingprofiles.zip"
    pack.write_input_zip(INPUT, dst, "DefaultRawGameControllerMappingProfileMOZACustom.xml", xml)
    with zipfile.ZipFile(dst) as z:
        names = z.namelist()
        assert "DefaultRawGameControllerMappingProfileMOZACustom.xml" in names
        assert "DefaultRawGameControllerMappingProfileLogitechG29.xml" in names  # stock kept
        assert all("/" not in n for n in names)
        assert all(i.compress_type == zipfile.ZIP_STORED for i in z.infolist())
        ET.fromstring(z.read("DefaultRawGameControllerMappingProfileMOZACustom.xml"))


def test_verify_store_only_top_level_pass(tmp_path):
    xml = build_profile_xml(full_capture_result())
    dst = tmp_path / "inputmappingprofiles.zip"
    pack.write_input_zip(INPUT, dst, "X.xml", xml)
    ok, bad = pack.verify_store_only_top_level(dst)
    assert ok and bad == []


def test_verify_catches_nested_and_deflated(tmp_path):
    bad_zip = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad_zip, "w") as z:
        z.writestr("top.xml", b"<a/>", compress_type=zipfile.ZIP_DEFLATED)   # compressed
        z.writestr("nested/inner.xml", b"<a/>", compress_type=zipfile.ZIP_STORED)  # nested
    ok, bad = pack.verify_store_only_top_level(bad_zip)
    assert not ok
    assert "top.xml" in bad and "nested/inner.xml" in bad


def test_backup_install_restore(tmp_path):
    media = tmp_path / "media"
    media.mkdir()
    (media / "inputmappingprofiles.zip").write_bytes(INPUT.read_bytes())
    (media / "wheeltunablesettingspc.zip").write_bytes(WHEEL.read_bytes())
    orig = (media / "inputmappingprofiles.zip").read_bytes()

    out_input = tmp_path / "out_in.zip"
    out_wheel = tmp_path / "out_wh.zip"
    out_input.write_bytes(b"PATCHED-INPUT")  # stand-ins; install just copies them
    out_wheel.write_bytes(b"PATCHED-WHEEL")

    bf = pack.install_zips(media, out_input, out_wheel)
    assert (bf / "inputmappingprofiles.zip").read_bytes() == orig  # backup is pristine
    assert (media / "inputmappingprofiles.zip").read_bytes() == b"PATCHED-INPUT"

    pack.restore_backup(media)
    assert (media / "inputmappingprofiles.zip").read_bytes() == orig  # restored
