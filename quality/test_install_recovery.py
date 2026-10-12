"""Process interruption, encoding and preservation tests using temporary targets only."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_agent_skill_distribution import ROOT, INSTALLER, file_sha, run_installer


CRASH_SCRIPT = r'''
import importlib.util, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]).parent))
spec = importlib.util.spec_from_file_location('installer', sys.argv[1])
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
original = os.replace
count = 0
def replace(source, destination):
    global count
    original(source, destination)
    if Path(source).name in {'mastery-coach', 'mastery-tool-creator'}:
        count += 1
        if count == int(sys.argv[3]): os._exit(73)
os.replace = replace
m.install_bundle(m.source_skills(m.load_manifest()), Path(sys.argv[2]), check=False, replace=True)
'''


class PortableRecoveryTests(unittest.TestCase):
    def test_unicode_target_returns_lossless_json_in_legacy_console(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / '测试技能'
            env = {**os.environ, 'PYTHONIOENCODING': 'cp1252', 'PYTHONUTF8': '0'}
            for arguments, status, code in [([], 'installed', 0), (['--check'], 'verified', 0)]:
                result = subprocess.run([sys.executable, str(INSTALLER), '--host', 'custom', '--target', str(target), *arguments],
                                        env=env, capture_output=True, text=True, encoding='ascii')
                self.assertEqual(result.returncode, code, result.stderr)
                report = json.loads(result.stdout)
                self.assertEqual(report['status'], status)
                self.assertEqual(Path(report['target']), target.resolve())
            (target / 'mastery-coach/SKILL.md').write_text('local edit', encoding='utf-8')
            result = subprocess.run([sys.executable, str(INSTALLER), '--host', 'custom', '--target', str(target)],
                                    env=env, capture_output=True, text=True, encoding='ascii')
            self.assertEqual(result.returncode, 1)
            self.assertEqual(json.loads(result.stdout)['status'], 'conflict')

    def test_hard_exit_at_every_replacement_move_restores_old_pair_on_retry(self):
        for boundary in range(1, 5):
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory() as temporary:
                target = Path(temporary) / 'skills'
                run_installer('--host', 'custom', '--target', target)
                paths = [target / name / 'SKILL.md' for name in ['mastery-coach', 'mastery-tool-creator']]
                for path in paths:
                    path.write_text(path.read_text(encoding='utf-8') + '\nlocal change\n', encoding='utf-8')
                old = [file_sha(path) for path in paths]
                crashed = subprocess.run([sys.executable, '-c', CRASH_SCRIPT, str(INSTALLER), str(target), str(boundary)], capture_output=True)
                self.assertEqual(crashed.returncode, 73, crashed.stderr)
                journal = target / '.mastery-tutor-transaction.json'
                journal_bytes = journal.read_bytes()
                checked = run_installer('--host', 'custom', '--target', target, '--check', expect=1)
                self.assertEqual(checked['status'], 'recovery-required')
                self.assertEqual(journal.read_bytes(), journal_bytes, '--check must not mutate the journal')
                recovered = run_installer('--host', 'custom', '--target', target, expect=1)
                self.assertTrue(recovered['recovered_interrupted_install'])
                self.assertEqual(recovered['status'], 'conflict')
                self.assertEqual([file_sha(path) for path in paths], old)
                self.assertFalse(journal.exists())
                self.assertEqual(list(Path(temporary).glob('.mastery-tutor-stage-*')), [])
                self.assertEqual(list(Path(temporary).glob('.mastery-tutor-backup-*')), [])

    def test_hard_exit_during_fresh_pair_can_retry(self):
        for boundary in [1, 2]:
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory() as temporary:
                target = Path(temporary) / 'skills'
                crashed = subprocess.run([sys.executable, '-c', CRASH_SCRIPT, str(INSTALLER), str(target), str(boundary)], capture_output=True)
                self.assertEqual(crashed.returncode, 73, crashed.stderr)
                report = run_installer('--host', 'custom', '--target', target)
                self.assertTrue(report['recovered_interrupted_install'])
                self.assertEqual(report['status'], 'installed')
                self.assertTrue(run_installer('--host', 'custom', '--target', target, '--check')['ok'])

    def test_changed_interrupted_target_is_never_discarded(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'skills'
            crashed = subprocess.run([sys.executable, '-c', CRASH_SCRIPT, str(INSTALLER), str(target), '1'], capture_output=True)
            self.assertEqual(crashed.returncode, 73)
            changed = target / 'mastery-coach/SKILL.md'
            changed.write_text('user edit after interruption', encoding='utf-8')
            result = subprocess.run([sys.executable, str(INSTALLER), '--host', 'custom', '--target', str(target)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(changed.read_text(encoding='utf-8'), 'user edit after interruption')
            self.assertTrue((target / '.mastery-tutor-transaction.json').is_file())

    def test_recovery_can_itself_be_interrupted_at_every_move(self):
        for boundary in range(1, 5):
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory() as temporary:
                target = Path(temporary) / 'skills'
                run_installer('--host', 'custom', '--target', target)
                paths = [target / name / 'SKILL.md' for name in ['mastery-coach', 'mastery-tool-creator']]
                for path in paths:
                    path.write_text(path.read_text(encoding='utf-8') + '\nold local edits\n', encoding='utf-8')
                old = [file_sha(path) for path in paths]
                for crash_boundary in [4, boundary]:
                    result = subprocess.run([sys.executable, '-c', CRASH_SCRIPT, str(INSTALLER), str(target), str(crash_boundary)], capture_output=True)
                    self.assertEqual(result.returncode, 73, result.stderr)
                report = run_installer('--host', 'custom', '--target', target, expect=1)
                self.assertTrue(report['recovered_interrupted_install'])
                self.assertEqual([file_sha(path) for path in paths], old)
                replaced = run_installer('--host', 'custom', '--target', target, '--replace')
                self.assertEqual(replaced['status'], 'installed')
                self.assertTrue(run_installer('--host', 'custom', '--target', target, '--check')['ok'])

    def test_commit_window_before_journal_clear_restores_previous_pair(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'skills'
            run_installer('--host', 'custom', '--target', target)
            for name in ['mastery-coach', 'mastery-tool-creator']:
                path = target / name / 'SKILL.md'
                path.write_text(path.read_text(encoding='utf-8') + '\nold release\n', encoding='utf-8')
            old = {name: file_sha(target / name / 'SKILL.md') for name in ['mastery-coach', 'mastery-tool-creator']}
            script = CRASH_SCRIPT[:CRASH_SCRIPT.index('original = os.replace')] + '''
original_unlink = Path.unlink
def unlink(path, *args, **kwargs):
    if path.name == '.mastery-tutor-transaction.json': os._exit(73)
    return original_unlink(path, *args, **kwargs)
Path.unlink = unlink
m.install_bundle(m.source_skills(m.load_manifest()), Path(sys.argv[2]), check=False, replace=True)
'''
            result = subprocess.run([sys.executable, '-c', script, str(INSTALLER), str(target)], capture_output=True)
            self.assertEqual(result.returncode, 73, result.stderr)
            report = run_installer('--host', 'custom', '--target', target, expect=1)
            self.assertTrue(report['recovered_interrupted_install'])
            self.assertEqual({name: file_sha(target / name / 'SKILL.md') for name in old}, old)

    def test_read_only_check_returns_busy_while_install_lock_is_held(self):
        sys.path.insert(0, str(ROOT))
        from install_transaction import installation_lock
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'skills'
            run_installer('--host', 'custom', '--target', target)
            with installation_lock(target):
                report = run_installer('--host', 'custom', '--target', target, '--check', expect=1)
                self.assertEqual(report['status'], 'busy')
            self.assertEqual(run_installer('--host', 'custom', '--target', target, '--check')['status'], 'verified')

    def test_malformed_journal_blocks_without_touching_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'skills'; target.mkdir()
            journal = target / '.mastery-tutor-transaction.json'
            journal.write_text('{broken', encoding='utf-8')
            report = run_installer('--host', 'custom', '--target', target, expect=1)
            self.assertEqual(report['status'], 'recovery-blocked')
            self.assertEqual(journal.read_text(), '{broken')
            self.assertFalse((target / 'mastery-coach').exists())

    def test_replace_refuses_non_directory_target_and_preserves_other_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'skills'; target.mkdir()
            occupied = target / 'mastery-coach'; occupied.write_text('unrelated file', encoding='utf-8')
            sentinel = target / '.mastery'; sentinel.mkdir()
            (sentinel / 'keep').write_text('learner data', encoding='utf-8')
            result = run_installer('--host', 'custom', '--target', target, '--replace', expect=1)
            self.assertEqual(result['status'], 'unsafe-target')
            self.assertEqual(occupied.read_text(), 'unrelated file')
            self.assertEqual((sentinel / 'keep').read_text(), 'learner data')
            self.assertFalse((target / 'mastery-tool-creator').exists())


if __name__ == '__main__':
    unittest.main()
