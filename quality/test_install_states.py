import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FAKE = '''import json, os, pathlib, sys
root = pathlib.Path(os.environ['MASTERY_FAKE_STATE'])
args = sys.argv[1:]
with (root/'calls.jsonl').open('a') as f: f.write(json.dumps(args)+'\\n')
source = root/'source.txt'
installed = root/'installed'
if args == ['--version']: print('codex-cli test')
elif args == ['plugin','marketplace','list']:
    if source.exists(): print('mastery-tutor '+source.read_text())
elif args[:3] == ['plugin','marketplace','add']:
    source.write_text('wrong-source' if os.environ.get('MASTERY_BAD_VERIFY') else args[3])
elif args[:2] == ['plugin','list']:
    if installed.exists(): print('mastery-tutor@mastery-tutor installed, enabled 0.5.0')
elif args == ['plugin','add','--help']: print('Usage: codex plugin add [OPTIONS]')
elif args == ['plugin','add','mastery-tutor@mastery-tutor']: installed.touch()
else: sys.exit(9)
'''

class InstallStateTests(unittest.TestCase):
    def run_install(self, *, source=None, cli=False, bad_verify=False):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path/'fake.py').write_text(FAKE, encoding='utf-8')
            if source is not None: (path/'source.txt').write_text(source, encoding='utf-8')
            env = dict(os.environ, MASTERY_FAKE_STATE=folder, CODEX_HOME=str(path/'codex'))
            if bad_verify: env['MASTERY_BAD_VERIFY'] = '1'
            if os.name == 'nt':
                fake = path/'fake.cmd'
                fake.write_text(f'@echo off\r\n"{sys.executable}" "{path / "fake.py"}" %*\r\nexit /b %errorlevel%\r\n', encoding='utf-8')
                command = [shutil.which('pwsh') or shutil.which('powershell'), '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(ROOT/'install.ps1'), '-CodexCommand', str(fake)]
                if cli: command += ['-UseCliInstall']
            else:
                fake = path/'fake'
                fake.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{path / "fake.py"}" "$@"\n', encoding='utf-8')
                fake.chmod(0o755)
                command = ['sh', str(ROOT/'install.sh'), '--codex', str(fake)]
                if cli: command += ['--use-cli-install']
            result = subprocess.run(command, env=env, capture_output=True, text=True, encoding='utf-8')
            calls = [json.loads(line) for line in (path/'calls.jsonl').read_text().splitlines()]
            return result, calls

    def test_fresh_registration_is_not_installation(self):
        result, calls = self.run_install()
        self.assertEqual(result.returncode, 2, result.stdout+result.stderr)
        self.assertIn('registered-awaiting-ui-install', result.stdout)
        self.assertEqual(sum(c[:3] == ['plugin','marketplace','add'] for c in calls), 1)
        self.assertFalse(any(c[:2] == ['plugin','add'] for c in calls))

    def test_conflicting_source_stops_before_write(self):
        result, calls = self.run_install(source=str(ROOT.parent/'other-source'))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('marketplace-source-conflict', result.stdout+result.stderr)
        self.assertFalse(any('add' in c for c in calls))

    def test_explicit_compatibility_flow_probes_then_installs(self):
        result, calls = self.run_install(cli=True)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertIn('MASTERY_INSTALL_STATUS=installed', result.stdout)
        self.assertLess(calls.index(['plugin','add','--help']), calls.index(['plugin','add','mastery-tutor@mastery-tutor']))

    def test_failed_registration_verification_never_installs(self):
        result, calls = self.run_install(cli=True, bad_verify=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(c[:2] == ['plugin','add'] for c in calls))
