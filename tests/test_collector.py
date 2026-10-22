import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('collector', Path(__file__).resolve().parents[1] / 'collector.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def table(f='45.000', s='28.000'):
    return f'noise\n| Name | Value | Parameter |\n| PPT LIMIT FAST | {f} | fast-limit |\n| PPT VALUE FAST | 1.234 | |\n| PPT LIMIT SLOW | {s} | slow-limit |\n'


class Tests(unittest.TestCase):
    def test_modes(self):
        for f, s in [('30', '10'), ('45', '28'), ('50', '30')]:
            self.assertEqual(c.parse_info(table(f, s)), {'fast': float(f), 'slow': float(s)})

    def test_reject(self):
        for text in ['', table('nan'), table('inf'), table('FAST'), table('-1'), table('0'),
                     table('151'), table('45,0'), table() + '| PPT LIMIT FAST | 45 | |']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                c.parse_info(text)

    def test_fixed_command(self):
        with patch.object(c, 'trusted'), patch.object(Path, 'read_text', return_value='TM2107\n'), \
             patch.object(c.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, table().encode())) as run:
            self.assertTrue(c.collect()['ok'])
            self.assertEqual(run.call_args.args[0], [str(c.BINARY), '--info'])
            self.assertEqual(run.call_args.kwargs['stderr'], subprocess.DEVNULL)
            self.assertEqual(run.call_args.kwargs['env'], c.ENV)

    def test_failures(self):
        with patch.object(c, 'trusted'), patch.object(Path, 'read_text', return_value='TM2107'):
            for effect in [subprocess.TimeoutExpired('x', 3), OSError('denied')]:
                with patch.object(c.subprocess, 'run', side_effect=effect):
                    self.assertFalse(c.collect()['ok'])
            with patch.object(c.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, b'')):
                self.assertEqual(c.collect()['error'], 'ryzenadj-failed')

    def test_board_guard(self):
        with patch.object(Path, 'read_text', return_value='other'), patch.object(c.subprocess, 'run') as run:
            self.assertFalse(c.collect()['ok'])
            run.assert_not_called()

    def test_atomic_publish(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(c, 'DIRECTORY', Path(temp)), patch.object(c, 'trusted'):
            target = Path(temp) / 'status.json'
            target.symlink_to(Path(temp) / 'victim')
            c.publish({'ok': False})
            self.assertFalse(target.is_symlink())
            self.assertEqual(json.loads(target.read_text()), {'ok': False})
            self.assertEqual(target.stat().st_mode & 0o777, 0o644)
            self.assertEqual(len(list(Path(temp).iterdir())), 1)

    def test_trust_rejects_symlinks_and_writable_files(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / 'x'
            p.symlink_to('/etc/passwd')
            with self.assertRaises(PermissionError):
                c.trusted(p)
            p.unlink()
            p.touch(mode=0o666)
            p.chmod(0o666)
            with self.assertRaises(PermissionError):
                c.trusted(p)


if __name__ == '__main__':
    unittest.main()
