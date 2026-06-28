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

The source is fully open, the build is reproducible (`build.ps1`), and you can verify any release on [VirusTotal](https://www.virustotal.com) yourself. As always, review code that modifies game files before running it.

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

```powershell
pip install -r requirements.txt       # runtime: textual + pygame
pip install -r requirements-dev.txt   # + pytest
python main.py                        # launch the TUI
python -m pytest -q                   # run the test suite
```

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
