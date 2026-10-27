import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('guard', Path(__file__).resolve().parents[1] / 'guard.py')
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)


def table(value):
    return 'noise\n| THM LIMIT CORE | %s | tctl-temp |\n' % value


class GuardTests(unittest.TestCase):
    def test_repair_and_verify(self):
        commands = []
        def run(option):
            commands.append(option)
            return table(98 if len(commands) == 1 else 85)
        self.assertEqual(g.enforce(run), {'before': 98, 'limit': 85, 'corrected': True})
        self.assertEqual(commands, ['--info', '--tctl-temp=85', '--info'])

    def test_preserve_lower_and_equal_limits(self):
        for value in (60, 75, 80, 85):
            commands = []
            def run(option):
                commands.append(option)
                return table(value)
            self.assertEqual(g.enforce(run)['limit'], value)
            self.assertEqual(commands, ['--info'])

    def test_invalid_readings_never_write(self):
        for value in ('nan', 'inf', '-1', '0', '126', '85,0', 'CORE'):
            commands = []
            def run(option):
                commands.append(option)
                return table(value)
            with self.assertRaises(ValueError):
                g.enforce(run)
            self.assertEqual(commands, ['--info'])
        for text in ('', table(85) + table(85)):
            with self.assertRaises(ValueError):
                g.parse_limit(text)

    def test_firmware_rejecting_limit_is_reported(self):
        def run(option):
            return table(98)
        with self.assertRaises(RuntimeError):
            g.enforce(run)

    def test_fixed_options_and_environment(self):
        with patch.object(g.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, b'info')) as run:
            self.assertEqual(g.run_option('--info'), 'info')
            self.assertEqual(run.call_args.args[0], [str(g.BINARY), '--info'])
            self.assertEqual(run.call_args.kwargs['env'], g.ENV)
        with self.assertRaises(ValueError):
            g.run_option('--fast-limit=65000')

    def test_timeout_and_failure_are_not_success(self):
        with patch.object(g.subprocess, 'run', side_effect=subprocess.TimeoutExpired('x', 3)):
            with self.assertRaises(subprocess.TimeoutExpired):
                g.run_option('--info')
        with patch.object(g.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, b'')):
            with self.assertRaises(RuntimeError):
                g.run_option('--info')


if __name__ == '__main__':
    unittest.main()
