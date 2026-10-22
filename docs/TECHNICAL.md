# Technical notes

[English](TECHNICAL.md) · [Русский](TECHNICAL.ru.md) · [Installation](../README.md)

## Hardware interfaces examined

Development machine: Linux Mint 22.3, Cinnamon 6.6.9, kernel 7.0.0-38-generic, DMI board_name TM2107. The redmi-wmi driver is bound to WMI GUID 46C93E13-EE9B-4262-8488-563BCA757FEF and exposes an input device. Neither `/sys/firmware/acpi/platform_profile` nor `/sys/class/platform-profile` was present. No current OEM mode attribute or hwmon pair for PPT Fast/Slow was found. Governors and RAPL are not treated as evidence of the OEM mode.

The examined ACPI SSDT7 dump handles event EV20/0x16 by cycling STNM 2 → 1 → 3 → 2 and invoking ECWT and HPTC. This project does not invoke those methods or write the EC.

The [upstream redmi-wmi driver](https://github.com/torvalds/linux/blob/master/drivers/platform/x86/redmi-wmi.c) converts OEM mode events to KEY_PERFORMANCE and has no platform_profile getter/setter. Keyboard events do not establish the initial state at login. The exact Ubuntu 7.0.0-38 driver source was not available for a source-level comparison; the upstream file is a reference, not proof of an identical build.

The [RyzenAdj API implementation](https://github.com/FlyGoat/RyzenAdj/blob/master/lib/api.c) requests SMU telemetry tables. `--info` does not set power limits but is not passive hardware reading. The existing installation used a /dev/mem fallback; no strictly read-only standard interface for this machine's current OEM mode was confirmed. This project does not install ryzen_smu or call unverified WMI commands.

## Collector and trust boundary

- systemd runs a root-owned copy of RyzenAdj with the single fixed argument `--info`, a sanitized environment, no input, a 3-second timeout, and discarded stderr.
- The Python parser splits table rows by `|` and matches the exact PPT LIMIT FAST/SLOW labels. Missing, duplicate, nonnumeric, nonfinite and implausible values are rejected.
- The collector accepts no command-line arguments, checks TM2107, and checks ownership/type/permissions on its executable path.
- Only a small JSON document is published, atomically, at `/run/redmi-mode/status.json`. The Cinnamon applet has no privileged command interface.
- No sudoers rule, setuid bit, executable capabilities, or user access to memory/PCI/EC is installed.

The systemd unit restricts filesystem writes. It deliberately does not enable PrivateDevices or ProtectKernelTunables because RyzenAdj may need /dev/mem and PCI configuration access. The hardware access remains privileged; this is not a read-only hardware sandbox. Trust the installed RyzenAdj build and its system library dependencies before copying it into the service directory.

`/usr/local`, `/usr/local/libexec`, `/usr/local/libexec/redmi-mode`, and the executable must be owned by root without group/world write access. The service copy is not automatically replaced when `/usr/local/bin/ryzenadj` changes. Stop both timer and service before replacing that copy.

## State and rendering

The applet uses asynchronous Gio reads every 2 seconds and starts no subprocesses. The oneshot collector runs approximately every 5–8 seconds. A timestamp older than 20 seconds, or over 2 seconds in the future, is rejected. Read failures clear the previous mode. Polling stops and pending IO is cancelled on applet removal. The independent system timer continues until stopped separately.

| Mode | Fast range, W | Slow range, W |
|---|---:|---:|
| Power saving | 28–32 | 9–11 |
| Balanced | 43–47 | 26–29 |
| Performance | 48–52 | 29–32 |
| Power saving (AC) | 33–37 | 18–22 |
| Balanced (AC) | 58–62 | 48–52 |
| Performance (AC) | 63–67 | 52–56 |

Other valid readings produce an unknown mode with the measured limits in the tooltip/menu. These ranges are empirical and do not read STNM. A tuning utility can change PPT independently of the firmware's selected mode. The indicator has three equal vertical bars, with one, two or three active. Messages use gettext with English source strings and a bundled Russian catalog bound to the applet-local locale directory.

## Tests

From the repository root, on a Mint system with `cjs`:

```sh
python3 -m unittest discover -s tests -v
LC_ALL=en_US.UTF-8 LANGUAGE=en cjs tests/test_applet.js "$PWD" en
LC_ALL=ru_RU.UTF-8 LANGUAGE=ru cjs tests/test_applet.js "$PWD" ru
systemd-analyze verify systemd/redmi-mode.service systemd/redmi-mode.timer
```

Seven Python tests and 49 CJS assertions per locale (English and Russian) passed on 2026-10-22. The CJS test uses real Gio/Cancellable asynchronous file IO with a mock Cinnamon shell surface. Tests cover parsing, classification boundaries, command errors/timeouts, fixed arguments, board guard, atomic publication, unsafe paths, freshness and cleanup. The unit verifier reported no errors for the project's units; the development host also emitted unrelated warnings about syncthing@.service.

GitHub Actions runs Python tests, JavaScript syntax checks, SVG/XML and JSON checks, and unit validation. The full CJS test runs locally on Mint; it is not part of the Ubuntu CI job.

Hardware evidence is limited to a successful 30/10 W sample, active timer and applet loading on one TM2107. The user confirmed the chosen icon appearance. A complete Fn+K cycle on AC was observed: 35/20 → 60/50 → 65/54 → 35/20 W. The extra ranges use a ±2 W tolerance around each AC pair, tested at their boundaries. Both limits must match the same range; the applet does not assume a mode from the charger state alone. Full battery cycling, AC/battery transitions, suspend/resume and actual battery impact have not been fully verified.

## Translations

Edit `po/ru.po` and rebuild the bundled catalog with GNU gettext (`sudo apt install gettext` if msgfmt is missing):

```sh
msgfmt --check po/ru.po -o applet/redmi-mode@local/locale/ru/LC_MESSAGES/redmi-mode@local-1.0.2.mo
```

Commit both files. CI checks that the binary catalog matches its source. The two locale tests require en_US.UTF-8 and ru_RU.UTF-8 (`locale -a` lists installed locales). A C locale disables gettext translations even with LANGUAGE=ru. The desktop session language preferences are used; log in again after changing the system language.
