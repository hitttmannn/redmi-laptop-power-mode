#!/usr/bin/python3
"""Fixed telemetry collector. No client-supplied paths, commands or arguments."""
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

DIRECTORY = Path('/run/redmi-mode')
BINARY = Path('/usr/local/libexec/redmi-mode/ryzenadj')
ENV = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL': 'C', 'HOME': '/'}


def parse_info(text):
    values = {}
    for line in text.splitlines():
        cells = [x.strip() for x in line.split('|')]
        if len(cells) < 4 or cells[1] not in ('PPT LIMIT FAST', 'PPT LIMIT SLOW'):
            continue
        key = 'fast' if cells[1].endswith('FAST') else 'slow'
        if key in values or not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', cells[2]):
            raise ValueError('invalid or duplicate PPT row')
        value = float(cells[2])
        if not math.isfinite(value) or not 0 < value <= 150:
            raise ValueError('PPT outside plausible range')
        values[key] = value
    if set(values) != {'fast', 'slow'}:
        raise ValueError('missing PPT rows')
    return values


def trusted(path, directory=False):
    st = path.lstat()
    expected = stat.S_ISDIR(st.st_mode) if directory else stat.S_ISREG(st.st_mode)
    if not expected or st.st_uid != 0 or st.st_mode & 0o022:
        raise PermissionError('unsafe owner, type or permissions: ' + str(path))


def collect():
    result = {'version': 1, 'timestamp': time.time(), 'source': 'ryzenadj --info',
              'ok': False, 'error': 'collector-error'}
    try:
        if Path('/sys/class/dmi/id/board_name').read_text().strip() != 'TM2107':
            raise ValueError('unsupported-board')
        for parent in (Path('/usr/local'), Path('/usr/local/libexec'), BINARY.parent):
            trusted(parent, True)
        trusted(BINARY)
        proc = subprocess.run([str(BINARY), '--info'], cwd='/', env=ENV,
                              stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, timeout=3, check=False)
        if proc.returncode:
            result['error'] = 'ryzenadj-failed'
        else:
            result.update(parse_info(proc.stdout.decode('utf-8', errors='replace')))
            result.update(ok=True, error='')
    except subprocess.TimeoutExpired:
        result['error'] = 'timeout'
    except (OSError, ValueError):
        result['error'] = 'unavailable-or-invalid-data'
    # Timestamp is the beginning of acquisition: a hung read cannot appear fresh.
    return result


def publish(result):
    trusted(DIRECTORY, True)
    fd, name = tempfile.mkstemp(prefix='.status-', dir=DIRECTORY)
    try:
        with os.fdopen(fd, 'w') as stream:
            os.fchmod(stream.fileno(), 0o644)
            json.dump(result, stream, allow_nan=False)
            stream.write('\n')
        os.replace(name, DIRECTORY / 'status.json')
    finally:
        if os.path.exists(name):
            os.unlink(name)


def main():
    if len(sys.argv) != 1 or os.geteuid() != 0:
        sys.exit('Run only through the installed system service; no arguments allowed.')
    publish(collect())


if __name__ == '__main__':
    main()
