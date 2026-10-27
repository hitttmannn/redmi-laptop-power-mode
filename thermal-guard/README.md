# Restore the 85 °C thermal ceiling automatically

[English](README.md) · [Русский](README.ru.md) · [Main installation guide](../README.md)

Optional temperature control for the Redmi Book Pro 14 2022, board **TM2107**, with redmi-mode and RyzenAdj already installed. Installing the panel applet alone does **not** enable this component.

## What it does

- Reads `THM LIMIT CORE` approximately every **30 seconds**.
- If the limit exceeds **85 °C**, sends only `--tctl-temp=85`, then verifies the result.
- Preserves lower firmware limits, such as 80 °C.
- Does not set power limits, clock speeds or Fn+K modes.
- Queues a separate check after suspend/hibernation resume.
- Uses `WakeSystem=no`: the timer does not wake the laptop. Checks still consume some energy while awake; battery impact has not been measured.

This is **periodic restoration**, not a continuous hardware-enforced 85 °C guarantee. Firmware can raise the limit between checks. After Fn+K or a power-source change, restoration normally occurs within about 30 seconds plus execution time. A configured threshold also does not rule out brief overshoots of actual CPU temperature.

The panel applet remains an unprivileged status reader. The telemetry collector and thermal guard use a shared lock to avoid simultaneous RyzenAdj commands. No direct EC/WMI writes, broad sudo rules, setuid binaries or extra user access to memory/PCI are installed.

## Installation

First install and verify the indicator using the [main guide](../README.md). This component uses its root-owned `/usr/local/libexec/redmi-mode/ryzenadj` copy.

Open a terminal in this `thermal-guard` folder, or run `cd thermal-guard` from the repository root. Check whether a temperature-limit service already exists:

```sh
systemctl cat ryzenadj.service
```

If the service is missing, install the supplied starting template. Do this only on a new installation; do not overwrite an existing service:

```sh
sudo install -o root -g root -m 0644 systemd/ryzenadj.service /etc/systemd/system/ryzenadj.service
```

If it already exists, skip that command. The installer expects the base service at `/etc/systemd/system/ryzenadj.service`; inspect other configurations before proceeding.

Review the component files and run:

```sh
sudo sh ./install.sh
```

It requires `ryzenadj.service`, `redmi-mode.service` and an active `redmi-mode.timer`. It refuses to overwrite its own existing installation files. If the first run fails, it removes the new files and restores original service behavior. Original units are copied into a root-only `/var/tmp/redmi-thermal-before-*` directory; its path is printed during installation.

The base unit files remain unchanged. Installation adds:

| Path | Purpose |
|---|---|
| `/usr/local/libexec/redmi-thermal-guard/guard.py` | Temperature check and correction |
| `/etc/systemd/system/ryzenadj.service.d/85c-guard.conf` | Replace the one-time command with the guard |
| `/etc/systemd/system/redmi-mode.service.d/30-thermal-lock.conf` | Shared lock for telemetry |
| `/etc/systemd/system/ryzenadj.timer` | 30-second schedule |
| `/usr/lib/systemd/system-sleep/85-redmi-thermal-guard` | Post-resume check |

## Verification

```sh
systemctl status ryzenadj.timer --no-pager
cat /run/redmi-mode/thermal.json
sudo journalctl -u ryzenadj.service -n 20 --no-pager
```

The timer should show `active (waiting)`. JSON should contain `"ok": true` and `"limit": 85.0` or a lower number. `timestamp` records the start of the last check; `corrected: true` means it restored the ceiling. This reports the last measurement, not a continuous guarantee.

1. Press Fn+K and wait about 35 seconds.
2. Inspect the JSON and journal. If firmware raised the threshold, a restoration message should appear.
3. Repeat for other modes, charger connection/disconnection and suspend/resume.

The oneshot **service** can show `inactive (dead)` between checks; that is normal. The **timer** should remain active. A failed check is reported as an error, with another attempt on the next cycle.

## Removal and rollback

Remove this component **before the main indicator**, because it uses the indicator's RyzenAdj copy and runtime directory.

```sh
sudo systemctl disable --now ryzenadj.timer
sudo systemctl stop ryzenadj.service
sudo rm -f /etc/systemd/system/ryzenadj.timer
sudo rm -f /etc/systemd/system/ryzenadj.service.d/85c-guard.conf
sudo rm -f /etc/systemd/system/redmi-mode.service.d/30-thermal-lock.conf
sudo rm -f /usr/lib/systemd/system-sleep/85-redmi-thermal-guard
sudo rm -f /usr/local/libexec/redmi-thermal-guard/guard.py
sudo rmdir /usr/local/libexec/redmi-thermal-guard
sudo systemctl daemon-reload
sudo systemctl restart ryzenadj.service
```

This restores the original one-time thermal service and leaves the indicator running. The optional template is also a one-time 85 °C service after rollback. `/run/redmi-mode/thermal.json` may be removed manually; it will no longer update.

## Tests and hardware evidence

From this folder:

```sh
python3 -m unittest discover -s tests -v
```

Six tests cover 98→85 restoration, lower thresholds, invalid input, unconfirmed correction, fixed commands/environment and failures/timeouts. They do not access hardware. CI runs these separately from the indicator tests and validates shell syntax and combined systemd units.

On 2026-10-27, an initial hardware reading was 98 °C; a reading after correction confirmed 85 °C. After Fn+K, the next automatic check found 90 °C and restored 85 °C, again verified by reading. Full acceptance testing across every mode, charger state and sleep state remains incomplete.
