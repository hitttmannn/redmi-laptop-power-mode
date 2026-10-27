# Automatic thermal target: 90 °C on AC, 80 °C on battery

[English](README.md) · [Русский](README.ru.md) · [Main installation guide](../README.md)

Optional temperature control for the Redmi Book Pro 14 2022, board **TM2107**, with redmi-mode and RyzenAdj already installed. Installing the panel applet alone does **not** enable this component.

## What it does

- Reads `THM LIMIT CORE` approximately every **30 seconds**.
- Reads the ACAD mains sensor and sets **90 °C on AC** or **80 °C on battery**, then verifies the result.
- Applies the selected target even if the previous limit was lower. If the power sensor is unreadable, uses 80 °C as a conservative ceiling and preserves any lower limit.
- Does not set power limits, clock speeds or Fn+K modes.
- Queues a check on AC connection/disconnection through udev, and after suspend/hibernation resume.
- Uses `WakeSystem=no`: the timer does not wake the laptop. Checks still consume some energy while awake; battery impact has not been measured.

This is **periodic restoration**, not a continuous hardware-enforced temperature guarantee. Firmware can raise the limit between checks. Power-source events trigger a check immediately. Firmware resets after Fn+K are corrected on the next periodic check, normally within about 30 seconds plus execution time. Missed power-source events are also covered by that timer. A configured threshold also does not rule out brief overshoots of actual CPU temperature.

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

The base unit files remain unchanged. The historical `85c-guard.conf` and `85-redmi-thermal-guard` filenames are retained for compatibility; their active policy is now 90/80 °C. Installation adds:

| Path | Purpose |
|---|---|
| `/usr/local/libexec/redmi-thermal-guard/guard.py` | Temperature check and correction |
| `/etc/systemd/system/ryzenadj.service.d/85c-guard.conf` | Replace the one-time command with the guard |
| `/etc/systemd/system/redmi-mode.service.d/30-thermal-lock.conf` | Shared lock for telemetry |
| `/etc/systemd/system/ryzenadj.timer` | 30-second schedule |
| `/usr/lib/systemd/system-sleep/85-redmi-thermal-guard` | Post-resume check |
| `/etc/udev/rules.d/90-redmi-thermal-power.rules` | ACAD power-change event |

## Verification

```sh
systemctl status ryzenadj.timer --no-pager
cat /run/redmi-mode/thermal.json
sudo journalctl -u ryzenadj.service -n 20 --no-pager
```

The timer should show `active (waiting)`. JSON should contain `"ok": true` and `"power_source": "ac"` with `"limit": 90.0`, or `"power_source": "battery"` with `"limit": 80.0`. `target` reports the selected target. An unreadable AC sensor is reported as `"power_source": "unknown"` and selects the safer 80 °C ceiling. `timestamp` records the start of the last check; `corrected: true` means it restored the ceiling. This reports the last measurement, not a continuous guarantee.

1. Press Fn+K and wait about 35 seconds.
2. Inspect the JSON and journal. If firmware raised the threshold, a restoration message should appear.
3. Repeat for other modes, charger connection/disconnection and suspend/resume.

The oneshot **service** can show `inactive (dead)` between checks; that is normal. The **timer** should remain active. A failed check is reported as an error, with another attempt on the next cycle.

## Updating an existing 85 °C installation

Do not run the fresh installer over an existing guard. From this folder, back up its files and replace them while the timer/service are stopped:

```sh
sudo systemctl stop ryzenadj.timer
sudo systemctl stop ryzenadj.service
sudo cp -p /usr/local/libexec/redmi-thermal-guard/guard.py /usr/local/libexec/redmi-thermal-guard/guard.py.before-90-80
sudo cp -p /etc/systemd/system/ryzenadj.service.d/85c-guard.conf /etc/systemd/system/ryzenadj.service.d/85c-guard.conf.before-90-80
sudo install -o root -g root -m 0644 guard.py /usr/local/libexec/redmi-thermal-guard/guard.py
sudo install -o root -g root -m 0644 systemd/85c-guard.conf /etc/systemd/system/ryzenadj.service.d/85c-guard.conf
sudo install -o root -g root -m 0644 systemd/ryzenadj.timer /etc/systemd/system/ryzenadj.timer
sudo install -o root -g root -m 0644 90-redmi-thermal-power.rules /etc/udev/rules.d/90-redmi-thermal-power.rules
sudo udevadm control --reload-rules
sudo systemctl daemon-reload
sudo systemctl start ryzenadj.service
sudo systemctl enable --now ryzenadj.timer
```

The `.before-90-80` backups are not loaded by systemd. Keep them for reference or remove them after verification. If you keep the Python backup in the installed directory, remove it before using `rmdir` during full uninstallation.

## Removal and rollback

Remove this component **before the main indicator**, because it uses the indicator's RyzenAdj copy and runtime directory.

```sh
sudo systemctl disable --now ryzenadj.timer
sudo systemctl stop ryzenadj.service
sudo rm -f /etc/systemd/system/ryzenadj.timer
sudo rm -f /etc/systemd/system/ryzenadj.service.d/85c-guard.conf
sudo rm -f /etc/systemd/system/redmi-mode.service.d/30-thermal-lock.conf
sudo rm -f /usr/lib/systemd/system-sleep/85-redmi-thermal-guard
sudo rm -f /etc/udev/rules.d/90-redmi-thermal-power.rules
sudo udevadm control --reload-rules
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

Ten tests cover AC/battery targets, raising the old 85 °C limit to 90 °C on AC, lowering to 80 °C on battery, a missing power sensor, a cable change during the transaction, invalid input, unconfirmed correction, fixed commands/environment and failures/timeouts. They do not access hardware. CI runs these separately from the indicator tests and validates shell syntax and combined systemd units.

On 2026-10-27, the original fixed 85 °C policy was verified after a Fn+K reset. The new policy was then verified on real hardware: 85→90 °C on AC, a firmware reset of 93→80 °C after unplugging, and 80→90 °C after reconnecting. The observed reconnection was handled within one 0.2-second monitoring interval. That observation is not a guaranteed latency. Full acceptance testing across every mode and sleep state remains incomplete.
