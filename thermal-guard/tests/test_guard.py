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


def simulated(initial, online):
    commands = []
    state = [initial]
    def run(option):
        commands.append(option)
        if option.startswith('--tctl-temp='):
            state[0] = int(option.split('=')[1])
        return table(state[0])
    return g.enforce(run, lambda: online), commands


class GuardTests(unittest.TestCase):
    def test_ac_sets_90_from_previous_85_or_firmware_98(self):
        for before in (80, 85, 98):
            result, commands = simulated(before, '1\n')
            self.assertEqual(result['limit'], 90)
            self.assertEqual(result['power_source'], 'ac')
            self.assertEqual(commands, ['--info', '--tctl-temp=90', '--info'])

    def test_battery_sets_80_after_ac_or_firmware_reset(self):
        for before in (85, 90, 98):
            result, commands = simulated(before, '0\n')
            self.assertEqual(result['limit'], 80)
            self.assertEqual(result['power_source'], 'battery')
            self.assertEqual(commands, ['--info', '--tctl-temp=80', '--info'])

    def test_no_write_when_target_matches(self):
        for limit, source in ((90, '1'), (80, '0')):
            result, commands = simulated(limit, source)
            self.assertFalse(result['corrected'])
            self.assertEqual(commands, ['--info'])

    def test_unknown_supply_uses_cooler_target(self):
        for source in ('', 'invalid', '2'):
            result, commands = simulated(98, source)
            self.assertEqual(result['limit'], 80)
            self.assertEqual(result['power_source'], 'unknown')
        result, commands = simulated(75, 'invalid')
        self.assertEqual(result['limit'], 75)
        self.assertEqual(commands, ['--info'])
        def missing():
            raise OSError('not present')
        self.assertEqual(g.power_policy(missing), {'power_source': 'unknown', 'target': 80})

    def test_unplug_during_transaction_is_rechecked(self):
        supply = iter(['1', '0', '0', '0'])
        commands = []
        limit = [98]
        def run(option):
            commands.append(option)
            if option.startswith('--tctl-temp='):
                limit[0] = int(option.split('=')[1])
            return table(limit[0])
        result = g.enforce(run, lambda: next(supply))
        self.assertEqual(result['power_source'], 'battery')
        self.assertEqual(result['limit'], 80)
        self.assertEqual(commands, ['--info', '--tctl-temp=90', '--info', '--info', '--tctl-temp=80', '--info'])

    def test_repeated_supply_changes_do_not_report_success(self):
        supply = iter(['1', '0', '0', '1'])
        def run(option):
            return table(90 if option == '--info' else 80)
        with self.assertRaises(RuntimeError):
            g.enforce(run, lambda: next(supply))

    def test_invalid_readings_never_write(self):
        for value in ('nan', 'inf', '-1', '0', '126', '85,0', 'CORE'):
            commands = []
            def run(option):
                commands.append(option)
                return table(value)
            with self.assertRaises(ValueError):
                g.enforce(run, lambda: '1')
            self.assertEqual(commands, ['--info'])
        for text in ('', table(85) + table(85)):
            with self.assertRaises(ValueError):
                g.parse_limit(text)

    def test_firmware_rejecting_limit_is_reported(self):
        with self.assertRaises(RuntimeError):
            g.enforce(lambda option: table(98), lambda: '1')

    def test_fixed_options_and_environment(self):
        for option in ('--info', '--tctl-temp=90', '--tctl-temp=80'):
            with patch.object(g.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, b'info')) as run:
                self.assertEqual(g.run_option(option), 'info')
                self.assertEqual(run.call_args.args[0], [str(g.BINARY), option])
                self.assertEqual(run.call_args.kwargs['env'], g.ENV)
        for option in ('--fast-limit=65000', '--tctl-temp=98', '--tctl-temp=85'):
            with self.assertRaises(ValueError):
                g.run_option(option)

    def test_timeout_and_failure_are_not_success(self):
        with patch.object(g.subprocess, 'run', side_effect=subprocess.TimeoutExpired('x', 3)):
            with self.assertRaises(subprocess.TimeoutExpired):
                g.run_option('--info')
        with patch.object(g.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, b'')):
            with self.assertRaises(RuntimeError):
                g.run_option('--info')


if __name__ == '__main__':
    unittest.main()
