# Redmi Laptop Power Mode

[English](README.md) · [Русский](README.ru.md)

A Cinnamon panel applet that shows the performance mode of the **Redmi Book Pro 14 2022 (TM2107)**. Switch modes with the laptop's **Fn + K** shortcut; the indicator updates automatically.

![Three-level panel indicator](assets/indicator-preview.svg)

| Bright bars | Mode | Earlier PPT Fast / Slow | On AC (verified cycle) |
|---|---|---|---|
| One | Power saving | 30 / 10 W | 35 / 20 W |
| Two | Balanced | 45 / 28 W | 60 / 50 W |
| Three | Performance | 50 / 30 W | 65 / 54 W |
| Question mark | Unknown | No fresh reading, a read error, or unfamiliar limits | — |

Hover over the icon for the mode name and power limits. Click it to open the menu. Wait about **10 seconds** after Fn + K for the display to update. The numbers are **power limits**, not the laptop's current power consumption. Mode detection is an estimate based on both limits; other tuning software can affect it.

## Requirements

- Linux Mint **22.3**, **Cinnamon** desktop; developed on Cinnamon **6.6.9** and kernel **7.0.0-38-generic**.
- Redmi Book Pro 14 2022 with DMI board name **TM2107**. The collector deliberately refuses other board names; other Redmi models are not validated.
- Python 3, systemd, and **RyzenAdj**. RyzenAdj is **not preinstalled by Linux Mint** and is **not included** in this repository. Installation is explained below.

Check the board name if unsure:

```sh
cat /sys/class/dmi/id/board_name
```

The expected result is `TM2107`.

## Installation

### 1. Open a terminal

Press **Ctrl + Alt + T**. Paste commands using **Ctrl + Shift + V**, then press Enter. Run the blocks in order. If a command fails, stop and save its error message.

Commands beginning with `sudo` request administrator access. Enter your account password when asked. The terminal shows no characters while you type the password; this is normal.

### 2. Install RyzenAdj

Already have a working `/usr/local/bin/ryzenadj`? Skip the build commands and run the check at the end of this step. Do not overwrite a working installation unnecessarily.

Otherwise, install the tools needed to build it:

```sh
sudo apt update
sudo apt install git build-essential cmake pkg-config libpci-dev python3
```

Download the source from the official RyzenAdj repository, build it as your normal user, and install the resulting executable:

```sh
mkdir -p ~/redmi-power-mode-build
cd ~/redmi-power-mode-build
git clone --depth 1 https://github.com/FlyGoat/RyzenAdj.git
cmake -S RyzenAdj -B RyzenAdj/build -DCMAKE_BUILD_TYPE=Release
cmake --build RyzenAdj/build --parallel 2
sudo install -o root -g root -m 0755 RyzenAdj/build/ryzenadj /usr/local/bin/ryzenadj
```

These commands adapt the [official Linux build instructions](https://github.com/FlyGoat/RyzenAdj#build); `pkg-config` is required by the current [CMake configuration](https://github.com/FlyGoat/RyzenAdj/blob/master/CMakeLists.txt). If the source folder already exists, use another empty build folder. The build downloads upstream's current code; future versions may behave differently.

Check that the installed program can read the power limits:

```sh
sudo /usr/local/bin/ryzenadj --info
```

Look for **PPT LIMIT FAST** and **PPT LIMIT SLOW** rows with numeric values. Diagnostic messages can appear alongside the table. If there is no table or access is denied, stop here and save the full output. Do not change memory permissions, disable kernel protection, or install an extra kernel module just to bypass an error. RyzenAdj needs hardware access, which some systems restrict.

This command requests information only; do not add power-setting options. No RyzenAdj automation or tuning services are needed for this applet.

### 3. Download this project

On this GitHub page, choose **Code → Download ZIP** and extract the archive. Open the extracted project folder: it should contain `collector.py`, `applet`, and `systemd`. Right-click an empty area of the folder and choose **Open in Terminal**.

Run all remaining installation commands in that terminal. Alternatively, if you use Git:

```sh
git clone https://github.com/hitttmannn/redmi-laptop-power-mode.git
cd redmi-laptop-power-mode
```

### 4. Install the panel applet

```sh
mkdir -p ~/.local/share/cinnamon/applets/redmi-mode@local
cp -R applet/redmi-mode@local/. ~/.local/share/cinnamon/applets/redmi-mode@local/
```

No output usually means the copy succeeded. Tooltips, menus and errors follow the session language: Russian is available, with English as the fallback. The compiled translation is included in the applet folder; no separate language installation is required. After changing the system language, log out and back in.

### 5. Install the background reader

The icon runs as your normal user. A small system service reads the hardware for it and publishes a status file. Review `collector.py` and the two `systemd/` files before installing them.

```sh
sudo install -d -o root -g root -m 0755 /usr/local/libexec/redmi-mode
sudo install -o root -g root -m 0755 /usr/local/bin/ryzenadj /usr/local/libexec/redmi-mode/ryzenadj
sudo install -o root -g root -m 0644 collector.py /usr/local/libexec/redmi-mode/collector.py
sudo install -o root -g root -m 0644 systemd/redmi-mode.service systemd/redmi-mode.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start redmi-mode.service
cat /run/redmi-mode/status.json
```

A successful reading contains **`"ok": true`** and numeric `fast` and `slow` fields. If it says `"ok": false`, use the troubleshooting section before continuing.

### 6. Enable automatic updates — required

Without this step, the first reading expires after 20 seconds and the icon changes to `?`.

```sh
sudo systemctl enable --now redmi-mode.timer
systemctl is-active redmi-mode.timer
```

The expected answer is **`active`**. Readings will update now and after subsequent boots, without a password prompt on each update.

### 7. Add the icon to the panel

1. Open **System Settings → Applets**.
2. Find **Redmi — Power Mode** (it may appear as **Redmi — режим производительности** in Russian).
3. Select it and press **+** to add it to the panel.
4. Wait about 10 seconds. Try Fn + K and wait again.

If it is missing from the list, save your work, log out, and log in again.

## Troubleshooting

Hover over `?` to read the reason. A short wait after login or resume is normal.

**Stale data (`Данные устарели`):** enable the timer and wait about 10 seconds:

```sh
sudo systemctl enable --now redmi-mode.timer
systemctl is-active redmi-mode.timer
```

**Reader missing (`Сборщик не установлен…`):** complete steps 5 and 6. If already installed, try `sudo systemctl start redmi-mode.service`.

**Reading failed (`Сборщик не получил PPT`):** collect these outputs when asking for help:

```sh
cat /run/redmi-mode/status.json
systemctl status redmi-mode.timer redmi-mode.service --no-pager
sudo journalctl -u redmi-mode.service -n 30 --no-pager
```

Include any “file not found” message too. Do not post passwords or SSH keys. The service intentionally discards RyzenAdj diagnostic noise; if its output is needed, stop the timer, run `sudo /usr/local/bin/ryzenadj --info` once, then start the timer again. Avoid frequent simultaneous hardware polling.

**Numbers are available but the mode is unknown:** both limits must match a known range. Press Fn + K, wait, and note the two values if the problem persists. Other power-tuning software may have changed them.

The menu item **Refresh readings** (**Обновить показания** in Russian) rereads the latest status file; it does not trigger an immediate hardware reading.

## Updating the applet

For an icon-only update, remove the applet from the panel, open a terminal in the new project folder, and repeat step 4. Add the applet again in Cinnamon settings. The service does not need reinstalling for an icon change.

The service has a separate, root-owned copy of RyzenAdj. Updating `/usr/local/bin/ryzenadj` does not update that copy automatically. After checking a new version, repeat the copy command from step 5 while the timer and service are stopped, then restart the timer. For collector or unit-file updates, stop the timer and service, repeat step 5, then step 6.

## Pausing and removal

Pause automatic readings:

```sh
sudo systemctl stop redmi-mode.timer
```

The icon will show `?` when its last reading expires. Resume with:

```sh
sudo systemctl start redmi-mode.timer
```

Removing the icon from the panel alone does **not** stop the background reader. To remove the whole project, first remove the applet from the panel, then run:

```sh
sudo systemctl disable --now redmi-mode.timer
sudo systemctl stop redmi-mode.service
sudo rm -f /etc/systemd/system/redmi-mode.service /etc/systemd/system/redmi-mode.timer
sudo systemctl daemon-reload
sudo rm -f /usr/local/libexec/redmi-mode/collector.py /usr/local/libexec/redmi-mode/ryzenadj
sudo rmdir /usr/local/libexec/redmi-mode
sudo rm -f /run/redmi-mode/status.json
sudo rmdir /run/redmi-mode
rm -r ~/.local/share/cinnamon/applets/redmi-mode@local
```

This leaves `/usr/local/bin/ryzenadj` and its source/build folder in place so other tools can continue using them.

## Hardware access and validation

The applet does not switch modes or set power limits. The system service runs one fixed command, `ryzenadj --info`, about every 5–8 seconds; the icon reads its status file every 2 seconds. No broad sudo rule, setuid executable, or direct EC write is installed. RyzenAdj telemetry still involves privileged SMU requests: this is **not strictly passive hardware reading**.

Validated on one TM2107: successful 30/10 W telemetry, running timer, and applet loading in Cinnamon. A complete Fn + K cycle on AC was observed: 35/20 → 60/50 → 65/54 → 35/20 W. Full battery cycling, automatic transitions between AC and battery, and suspend/resume still need a complete hardware acceptance test. Automated tests cover the parser and applet state/IO logic, not the firmware.

See [technical notes and tests](docs/TECHNICAL.md). Project code is under the [MIT license](LICENSE). RyzenAdj is a separate upstream project with its own license; its executable is not shipped here.
