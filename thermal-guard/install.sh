#!/bin/sh
set -eu
if [ "$(id -u)" != 0 ]; then
    echo 'Run this installer as administrator.' >&2
    exit 1
fi
package_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
[ "$(cat /sys/class/dmi/id/board_name)" = TM2107 ]
[ -x /usr/local/libexec/redmi-mode/ryzenadj ]
[ -f /usr/local/libexec/redmi-mode/collector.py ]
[ -f /etc/systemd/system/ryzenadj.service ]
[ -f /etc/systemd/system/redmi-mode.service ]
for target in /usr/local/libexec/redmi-thermal-guard/guard.py \
    /etc/systemd/system/ryzenadj.service.d/85c-guard.conf \
    /etc/systemd/system/redmi-mode.service.d/30-thermal-lock.conf \
    /etc/systemd/system/ryzenadj.timer \
    /usr/lib/systemd/system-sleep/85-redmi-thermal-guard; do
    if [ -e "$target" ]; then
        echo "Already exists; not replacing: $target" >&2
        exit 1
    fi
done
systemctl is-active --quiet redmi-mode.timer
# Save the original units for reference. They remain unchanged by this installer.
backup_dir=$(mktemp -d /var/tmp/redmi-thermal-before-XXXXXXXX)
chmod 0700 "$backup_dir"
cp -p /etc/systemd/system/ryzenadj.service /etc/systemd/system/redmi-mode.service "$backup_dir/"
echo "Original service backup: $backup_dir"
rollback() {
    code=$?
    trap - EXIT HUP INT TERM
    if [ "$code" -ne 0 ]; then
        echo 'Installation failed; removing this installation and restoring original units.' >&2
        systemctl disable --now ryzenadj.timer 2>/dev/null || true
        systemctl stop ryzenadj.service 2>/dev/null || true
        rm -f /etc/systemd/system/ryzenadj.service.d/85c-guard.conf \
            /etc/systemd/system/redmi-mode.service.d/30-thermal-lock.conf \
            /etc/systemd/system/ryzenadj.timer \
            /usr/lib/systemd/system-sleep/85-redmi-thermal-guard \
            /usr/local/libexec/redmi-thermal-guard/guard.py
        systemctl daemon-reload
        systemctl restart ryzenadj.service 2>/dev/null || true
    fi
    exit "$code"
}
trap rollback EXIT
trap 'exit 1' HUP INT TERM
install -d -o root -g root -m 0755 /usr/local/libexec/redmi-thermal-guard \
    /etc/systemd/system/ryzenadj.service.d /etc/systemd/system/redmi-mode.service.d
install -o root -g root -m 0644 "$package_dir/guard.py" /usr/local/libexec/redmi-thermal-guard/guard.py
install -o root -g root -m 0644 "$package_dir/systemd/85c-guard.conf" /etc/systemd/system/ryzenadj.service.d/85c-guard.conf
install -o root -g root -m 0644 "$package_dir/systemd/30-thermal-lock.conf" /etc/systemd/system/redmi-mode.service.d/30-thermal-lock.conf
install -o root -g root -m 0644 "$package_dir/systemd/ryzenadj.timer" /etc/systemd/system/ryzenadj.timer
install -o root -g root -m 0755 "$package_dir/85c-resume" /usr/lib/systemd/system-sleep/85-redmi-thermal-guard
systemctl daemon-reload
# Wait for a pre-update telemetry run to finish before the first guarded access.
while systemctl is-active --quiet redmi-mode.service; do sleep 0.1; done
systemctl restart ryzenadj.service
systemctl enable --now ryzenadj.timer
systemctl is-active --quiet ryzenadj.timer
cat /run/redmi-mode/thermal.json
echo 'Installed: 85 C ceiling, 30-second checks, no waking from sleep.'
