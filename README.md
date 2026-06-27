# Horizon Wheel TUI

A terminal UI for configuring a sim racing wheel in **Forza Horizon 6** — no hand-editing XML required. 🐾

A Python/Textual port of [irpina/HorizonWheelWizard](https://github.com/irpina/HorizonWheelWizard), with improvements.

## AI Disclosure

Built with Claude (Anthropic, Claude Sonnet 4.6 and Opus 4.8 via Claude Code).
The upstream [HorizonWheelWizard](https://github.com/irpina/HorizonWheelWizard) was also built with Claude;
the original [Horizon-SimTool](https://github.com/Dxniel02/Horizon-SimTool) that started it all was built with OpenAI Codex.

Review the code before relying on it. This tool modifies game files — always verify your backups.

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
- Python 3.10+
- A supported sim racing wheel connected via USB

## Notes

Device silencing requires running as Administrator. Profile generation and testing work without elevation.
