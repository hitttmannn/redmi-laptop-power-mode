#!/usr/bin/python3
"""Maintain a ceiling of 85 C. Never change power limits or raise lower thermal limits."""
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
CEILING = 85.0


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
    if option not in ('--info', '--tctl-temp=85'):
        raise ValueError('unsupported command')
    result = subprocess.run([str(BINARY), option], cwd='/', env=ENV,
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, timeout=3, check=False)
    if result.returncode:
        raise RuntimeError('RyzenAdj failed (exit %d)' % result.returncode)
    return result.stdout.decode('utf-8', errors='replace')


def enforce(run=run_option):
    before = parse_limit(run('--info'))
    if before <= CEILING:
        return {'before': before, 'limit': before, 'corrected': False}
    run('--tctl-temp=85')
    after = parse_limit(run('--info'))
    if after > CEILING:
        raise RuntimeError('firmware did not retain the 85 C ceiling')
    return {'before': before, 'limit': after, 'corrected': True}


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
    report = {'version': 1, 'timestamp': time.time(), 'ok': False, 'ceiling': CEILING}
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
            print('Restored thermal limit: %.1f -> %.1f C' % (report['before'], report['limit']), flush=True)
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
