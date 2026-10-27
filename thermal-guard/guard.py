#!/usr/bin/python3
"""Apply a 90 C AC / 80 C battery thermal target without changing power limits."""
import fcntl
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import time

BINARY = Path('/usr/local/libexec/redmi-mode/ryzenadj')
RUNTIME = Path('/run/redmi-mode')
ENV = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL': 'C', 'HOME': '/'}
AC_LIMIT = 90.0
BATTERY_LIMIT = 80.0
AC_ONLINE = Path('/sys/class/power_supply/ACAD/online')


def parse_limit(text):
    values = []
    for line in text.splitlines():
        cells = [cell.strip() for cell in line.split('|')]
        if len(cells) >= 4 and cells[1] == 'THM LIMIT CORE':
            if not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', cells[2]):
                raise ValueError('invalid thermal limit')
            value = float(cells[2])
            if not math.isfinite(value) or not 0 < value <= 125:
                raise ValueError('implausible thermal limit')
            values.append(value)
    if len(values) != 1:
        raise ValueError('missing or duplicate thermal limit')
    return values[0]


def run_option(option):
    # No shell, no arbitrary arguments, no inherited environment.
    if option not in ('--info', '--tctl-temp=90', '--tctl-temp=80'):
        raise ValueError('unsupported command')
    result = subprocess.run([str(BINARY), option], cwd='/', env=ENV,
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, timeout=3, check=False)
    if result.returncode:
        raise RuntimeError('RyzenAdj failed (exit %d)' % result.returncode)
    return result.stdout.decode('utf-8', errors='replace')


def power_policy(read_online=None):
    try:
        online = (read_online or AC_ONLINE.read_text)().strip()
        if online == '1':
            return {'power_source': 'ac', 'target': AC_LIMIT}
        if online == '0':
            return {'power_source': 'battery', 'target': BATTERY_LIMIT}
    except OSError:
        pass
    # A missing/unreliable supply sensor must not select the hotter AC target.
    return {'power_source': 'unknown', 'target': BATTERY_LIMIT}


def enforce(run=run_option, read_online=None):
    original = None
    corrected = False
    for attempt in range(2):
        policy = power_policy(read_online)
        before = parse_limit(run('--info'))
        if original is None:
            original = before
        target = policy['target']
        needs_update = before != target
        if policy['power_source'] == 'unknown' and before <= target:
            needs_update = False
        after = before
        if needs_update:
            run('--tctl-temp=%d' % target)
            corrected = True
            after = parse_limit(run('--info'))
        # If a cable changed during the transaction, apply the newly selected
        # policy before reporting success. The timer covers later changes too.
        if power_policy(read_online) != policy:
            continue
        valid = after <= target if policy['power_source'] == 'unknown' else after == target
        if not valid:
            raise RuntimeError('firmware did not retain the %d C target' % target)
        return {'before': original, 'limit': after, 'corrected': corrected, **policy}
    raise RuntimeError('power source kept changing during the check')


def trust(path, directory=False):
    info = path.lstat()
    valid_type = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    if not valid_type or info.st_uid != 0 or info.st_mode & 0o022:
        raise PermissionError('unsafe owner, type or permissions: ' + str(path))


def locked():
    fd = os.open(RUNTIME / 'smu.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o644)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022 or info.st_nlink != 1:
            raise PermissionError('unsafe lock file')
        deadline = time.monotonic() + 4
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return fd
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError('timed out waiting for telemetry lock')
                time.sleep(0.05)
    except BaseException:
        os.close(fd)
        raise


def publish(data):
    fd, temp = tempfile.mkstemp(prefix='.thermal-', dir=RUNTIME)
    try:
        with os.fdopen(fd, 'w') as stream:
            os.fchmod(stream.fileno(), 0o644)
            json.dump(data, stream, allow_nan=False)
            stream.write('\n')
        os.replace(temp, RUNTIME / 'thermal.json')
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def main():
    if len(sys.argv) != 1 or os.geteuid() != 0:
        raise SystemExit('Run only through the system service; no arguments accepted.')
    trust(RUNTIME, True)
    report = {'version': 1, 'timestamp': time.time(), 'ok': False}
    lock = None
    try:
        if Path('/sys/class/dmi/id/board_name').read_text().strip() != 'TM2107':
            raise RuntimeError('unsupported board')
        for parent in (Path('/usr/local'), Path('/usr/local/libexec'), BINARY.parent):
            trust(parent, True)
        trust(BINARY)
        lock = locked()
        report.update(enforce())
        report['ok'] = True
        if report['corrected']:
            print('Thermal limit: %.1f -> %.1f C (%s)' % (report['before'], report['limit'], report['power_source']), flush=True)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        report['error'] = str(error)
        print('Thermal guard: ' + str(error), file=sys.stderr, flush=True)
    finally:
        if lock is not None:
            os.close(lock)
    publish(report)
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
