# Horizon Wheel TUI

A terminal UI for configuring a sim racing wheel in **Forza Horizon 6** — no hand-editing XML required. 🐾

A Python/Textual port of [irpina/HorizonWheelWizard](https://github.com/irpina/HorizonWheelWizard), with improvements.

## AI Disclosure

Built with Claude (Anthropic, Claude Sonnet 4.6 and Opus 4.8 via Claude Code).
The upstream [HorizonWheelWizard](https://github.com/irpina/HorizonWheelWizard) was also built with Claude;
the original [Horizon-SimTool](https://github.com/Dxniel02/Horizon-SimTool) that started it all was built with OpenAI Codex.

**Why AI?** Forza's wheel configuration lives in undocumented XML profiles and INI templates
packed inside the game's media ZIPs — dozens of `INPUTCMD_*` keys fanned out across ten input
contexts, a force-feedback format with no spec, and per-device VID/PID quirks that fail silently
when you get them wrong. There is no official documentation for any of it. Working that out by
hand means staring at confusing settings files and guessing. AI was used to reverse-engineer the
format from the shipped profiles, faithfully port the existing C# logic to Python, and capture the
hard-won details (like the mandatory `0x` VID/PID prefix) in tests and comments so they don't get
lost again. The goal: turn a fragile, manual, error-prone process into something repeatable that a
person without a reverse-engineering background can actually use.

Review the code before relying on it. This tool modifies game files — always verify your backups.

## Download

Grab the latest build from the [Releases](https://github.com/SanyaMine/horizon-wheel-tui/releases) page. Two flavors:

- **`horizon-wheel-tui.exe`** — standalone single-file executable. Download and run; nothing to install.
- **`horizon-wheel-tui-portable.zip`** — portable folder build. Extract anywhere and run `horizon-wheel-tui.exe` from inside. Starts a little faster and trips fewer antivirus heuristics than the single-file build.

Prefer not to trust a binary? Run it [from source](#setup) — it's a short Python program.

### A note on antivirus warnings

Both builds are packaged with [PyInstaller](https://pyinstaller.org), which bundles Python and the app into a Windows `.exe`. PyInstaller's bootloader is shared by countless legitimate apps **and** by some malware, so a handful of heuristic antivirus engines flag *the packaging method*, not anything this app does — a textbook false positive. The single-file `.exe` (which unpacks itself to a temp folder at launch) trips more engines than the portable zip.

The source is fully open, the build is reproducible (`python build.py`), and you can verify any release on [VirusTotal](https://www.virustotal.com) yourself. As always, review code that modifies game files before running it.

## Credits

This project stands on the shoulders of two people who did the hard reverse-engineering work first:

**[irpina/HorizonWheelWizard](https://github.com/irpina/HorizonWheelWizard)** — the direct upstream.
The core of this tool is a faithful Python port of irpina's C# implementation: the 26-input
mapping wizard, the full XML profile builder with its ten input contexts, the FFB INI patching,
the ZIP repack/backup/install pipeline, and the Quick Remap mode. None of this would exist without
that work. MIT licensed.

**[Dxniel02/Horizon-SimTool](https://github.com/Dxniel02/Horizon-SimTool)** — the pioneer.
Dxniel02's tool was the first to crack the problem of mapping arbitrary wheelbases to FH6,
establishing the device silencing approach, the HST-BACKUP system, and preset management that
both tools share. MIT licensed.

Go give their repos a star. 🌟

## What it does

Walks you through 26 live input captures from your wheel, then builds a complete
`RawGameController` input-mapping profile and patches the game's media ZIPs — no
game files are modified without a backup first.

**Also included:**
- **Quick mode** — clone a shipped profile and re-VID/PID it to your wheel, skipping full capture
- **Remap mode** — reload a saved preset and re-record only the controls you click
- **Device Silencing** — disable phantom/duplicate HID devices so Forza picks the right one

## Improvements over upstream

- Full **hat/POV d-pad** support (`InputType="Switch"`) — wheels like the Moza R3 with no nav buttons work out of the box
- **Stable profile IDs** — re-installs overwrite the same profile slot instead of spawning a new GUID each time
- **Post-install self-check** — verifies the profile is actually present in the ZIP after install
- **Wider mappings** opt-in — adds H-pattern gears, brake-as-left-trigger, and `PROP_PLACEMENT_UI` context (off by default, byte-identical output when disabled)
- Broadened FFB INI regex — correctly patches the generic `ControllerFFB-0000000000.ini` fallback template
- Pure Python + [Textual](https://github.com/Textualize/textual) TUI — no WinForms/WebView2 required

## Setup

```bash
pip install -r requirements.txt       # runtime: textual + pygame
pip install -r requirements-dev.txt   # + pytest
python main.py                        # launch the TUI
python -m pytest -q                   # run the test suite
```

## Building from source

`build.py` packages the app into distributable artifacts with [PyInstaller](https://pyinstaller.org).
It's pure standard-library Python and runs on Windows, Linux, and macOS — the executable it
produces is native to whatever OS you build on (a `.exe` only on Windows).

```bash
python build.py                 # build both: standalone executable + portable .zip
python build.py --target exe    # single-file dist/horizon-wheel-tui[.exe] only
python build.py --target zip    # portable dist/horizon-wheel-tui-portable.zip only
python build.py --clean         # remove build/ and dist/ before building
```

Outputs land in `dist/`:

- **`horizon-wheel-tui[.exe]`** — standalone single-file executable.
- **`horizon-wheel-tui-portable.zip`** — the folder build zipped, top-level folder preserved.

PyInstaller installs itself automatically on first run if it isn't already present. It logs
progress to stderr — that's normal; success is decided by exit code, not by stderr output.

**`build.py` does not cross-compile.** PyInstaller bundles the local interpreter and native
libraries, so you get a binary for the OS you build on — a Windows `.exe` must be built on
Windows, running it on Linux produces a Linux binary, and so on. The script is portable; the
artifacts are per-platform.

## Requirements

- Windows (device enumeration and install are Windows-only; profile generation is portable)
- Python 3.10+ (only if running from source — the release builds bundle it)
- A sim racing wheel connected via USB

## Wheel compatibility

Forza Horizon 6's official wheel support is patchy — see Microsoft's
[FH6 Supported Wheels and Devices](https://support.forza.net/hc/en-us/articles/51674028831251-FH6-Supported-Wheels-and-Devices)
list. Many popular wheels are unsupported or only partially supported out of the box (no force
feedback, no menu navigation, or simply not detected). **That gap is the whole reason this tool
exists:** by building a `RawGameController` profile keyed to your exact device, it gets wheels
working that the game won't configure on its own — but results vary by hardware, and a wheel
Microsoft lists as unsupported may still have rough edges (e.g. no native FFB template, so a
generic one is used). Your mileage may vary.

## Notes

Device silencing requires running as Administrator. Profile generation and testing work without elevation.

## Disclaimer

**Use this application at your own risk.**

Back up your game files before using this tool. Horizon Wheel TUI includes backup and restore
features, but you are responsible for verifying your own backups before installing generated files.

This application can modify files in your game installation folder. It can also disable
controller-class devices system-wide while device silencing is active. If you select the wrong
device, use an incorrect game folder, overwrite files, restore the wrong backup, or run into a
system-specific issue, your game configuration, controller behavior, Windows device state, or other
local files may be affected.

The authors are not responsible for anything that happens from using this application. This includes,
but is not limited to, broken game files, lost settings, disabled devices, game crashes, Windows
issues, hardware behavior changes, data loss, account issues, bans, lost time, or any other damage or
inconvenience.

This project is not affiliated with, endorsed by, sponsored by, or supported by Microsoft, Xbox,
Playground Games, Turn 10 Studios, Forza, Steam, Valve, MOZA, or any hardware manufacturer.

Forza, Xbox, Microsoft, Steam, MOZA, and all other names, trademarks, and brands belong to their
respective owners.

This software is provided as-is, with no warranty of any kind.
