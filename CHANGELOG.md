# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0] - 2026-08-30

### Fixed
- **Second device's inputs were silently mapped to the wheelbase** ([#1]). On a multi-device rig
  (wheelbase + button hub / shifter / handbrake), every binding was written with the wheelbase's
  VID/PID, so the second device's controls did nothing in-game despite the icons looking correct.
  Capture now reads each input's real VID/PID from the device that produced it (the SDL joystick
  GUID) instead of guessing from the controller name.

### Added
- **Official Moza Pit House FFB presets bundled.** The five official per-model tunes
  (R3 / R5 / R9 / R12 / R16-21) are selectable as FFB templates for any wheel — the installer
  re-patches `VendorProduct` to whatever wheel is installed — and are **auto-selected** when the
  connected wheel's VID/PID matches (e.g. an R3 reporting `0x346E0005`).
- **Xbox-default hints during capture.** Each control shows where it lives on FH6's default Xbox
  layout (e.g. *Gas → RT · right trigger*), verified against the FH6 control guides. Manual drivers
  are told **Shift Down ships unbound**.
- **ASCII shifter-gate diagram for H-pattern gears**, showing both the **standard** and **dogleg**
  layouts with the current gear highlighted (R and 1–7).
- **Welcome-screen warning for Moza Forza-compat mode.** Shown in red when a wheel is detected in
  Moza Pit House's "Base Forza Horizon Compatibility" mode (`0x346E0015`), which breaks FH6 — with a
  reminder to turn it off.

## [2.0.2] - 2026-07-08

Maintenance release. See the [GitHub release notes][2.0.2-rel].

## [2.0.1] - 2026-06-28

Maintenance release. See the [GitHub release notes][2.0.1-rel].

## [2.0.0] - 2026-06-27

Initial public release: Textual TUI that builds a Forza Horizon input-mapping profile from live
wheel capture (or a Quick-mode clone), patches the FFB INI, and repacks the game media ZIPs with a
backup. See the [GitHub release notes][2.0.0-rel].

[#1]: https://github.com/k0y4v2/horizon-wheel-tui/issues/1
[2.1.0]: https://github.com/k0y4v2/horizon-wheel-tui/compare/v2.0.2...v2.1.0
[2.0.2]: https://github.com/k0y4v2/horizon-wheel-tui/compare/v2.0.1...v2.0.2
[2.0.1]: https://github.com/k0y4v2/horizon-wheel-tui/compare/v2.0.0...v2.0.1
[2.0.0]: https://github.com/k0y4v2/horizon-wheel-tui/releases/tag/v2.0.0
[2.0.2-rel]: https://github.com/k0y4v2/horizon-wheel-tui/releases/tag/v2.0.2
[2.0.1-rel]: https://github.com/k0y4v2/horizon-wheel-tui/releases/tag/v2.0.1
[2.0.0-rel]: https://github.com/k0y4v2/horizon-wheel-tui/releases/tag/v2.0.0
