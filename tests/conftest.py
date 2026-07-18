"""Session setup: auto-provision the copyrighted game-data ZIPs for the test suite.

`inputmappingprofiles.zip` and `wheeltunablesettingspc.zip` are real Forza media files —
copyrighted, so they can't live in the repo. Instead of hand-placing them, we locate a
local Forza install (reusing the same detection the app uses, `hwt.forza.find_media_folders`)
and copy the two ZIPs into tests/gamedata/. If no install is found, the folder stays empty
and the game-data-dependent tests skip themselves via their module-level `pytestmark`.

`pytest_configure` runs before test modules are collected/imported, so the files are in
place before those modules evaluate their `INPUTMAPPING_ZIP.exists()` skip guards.
"""
from __future__ import annotations

import shutil

from hwt import forza
from tests.fixtures import GAMEDATA_DIR, INPUTMAPPING_ZIP, WHEELTUNABLE_ZIP


def pytest_configure(config):
    folders = forza.find_media_folders()
    if not folders:
        return  # no Forza install detected — game-data tests will skip
    media = folders[0]
    GAMEDATA_DIR.mkdir(parents=True, exist_ok=True)
    for name, dest in ((forza.INPUT_ZIP, INPUTMAPPING_ZIP), (forza.WHEEL_ZIP, WHEELTUNABLE_ZIP)):
        src = media / name
        # Refresh when missing or stale so a game update flows through to the fixtures.
        if src.exists() and (not dest.exists() or src.stat().st_mtime > dest.stat().st_mtime):
            shutil.copy2(src, dest)
