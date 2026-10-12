"""Recover interrupted portable installs; not atomic visibility for a running host.

The host must be closed. Advisory locks serialize cooperating installers. Unknown,
modified, or linked recovery artifacts stop recovery rather than being overwritten.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import shutil
import stat
from pathlib import Path

JOURNAL = '.mastery-tutor-transaction.json'
LOCK = '.mastery-tutor-install.lock'


class RecoveryError(ValueError):
    """Recovery cannot safely interpret or restore the pending transaction."""


class InstallBusyError(RuntimeError):
    """A cooperating installer currently owns the target lock."""


def exists(path: Path) -> bool:
    return os.path.lexists(path)


def transaction_paths(root: Path, identifier: str) -> tuple[Path, Path]:
    # Targets sharing a parent must never consume each other's recovery artifacts.
    key = hashlib.sha256(os.path.normcase(str(root.resolve())).encode('utf-8')).hexdigest()[:16]
    suffix = key + '-' + identifier
    return root.parent / ('.mastery-tutor-stage-' + suffix), root.parent / ('.mastery-tutor-backup-' + suffix)


def reject_link(path: Path) -> None:
    if not exists(path):
        return
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0):
        raise SystemExit(f'Linked transaction path is unsafe: {path}')


@contextlib.contextmanager
def installation_lock(root: Path, *, create: bool = True):
    if create:
        root.mkdir(parents=True, exist_ok=True)
    path = root / LOCK
    reject_link(path)
    if not create and not exists(path):
        yield False
        return
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT if create else os.O_RDONLY, 0o600)
    acquired = False
    try:
        if create and os.fstat(descriptor).st_size == 0:
            os.write(descriptor, b'0')
        os.lseek(descriptor, 0, os.SEEK_SET)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError as error:
            raise InstallBusyError('Another installer holds this target; retry after it exits.') from error
        yield True
    finally:
        if acquired:
            if os.name == 'nt':
                import msvcrt
                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)
        # Keep the lock inode: deleting it lets another process lock a different file.


def write_journal(root: Path, transaction: dict) -> None:
    path = root / JOURNAL
    temporary = root / ('.mastery-tutor-journal-' + transaction['id'] + '.tmp')
    if exists(path):
        raise RecoveryError('A recovery journal already exists; refusing to overwrite it.')
    with temporary.open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(transaction, handle, ensure_ascii=True, indent=2)
        handle.write('\n')
        handle.flush()
        os.fsync(handle.fileno())
    # Publishing complete bytes first avoids a truncated authoritative journal after a kill.
    os.replace(temporary, path)


def recover(root: Path, names: set[str], digest) -> bool:
    path = root / JOURNAL
    if not exists(path):
        return False
    reject_link(path)
    if not path.is_file() or path.stat().st_size > 16384:
        raise RecoveryError(f'Invalid recovery journal; preserve artifacts for manual review: {path}')
    try:
        transaction = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        raise RecoveryError(f'Unreadable recovery journal; no automatic changes: {path}') from error
    if not isinstance(transaction, dict) or set(transaction) != {'version', 'id', 'skills'} or transaction['version'] != 1:
        raise RecoveryError('Invalid recovery journal schema; no automatic changes.')
    identifier = transaction['id']
    records = transaction['skills']
    if not isinstance(identifier, str) or not re.fullmatch('[0-9a-f]{32}', identifier) or not isinstance(records, list) or not records:
        raise RecoveryError('Invalid recovery transaction identity; no automatic changes.')
    stage, backup = transaction_paths(root, identifier)
    reject_link(stage); reject_link(backup)
    seen = set()
    for record in records:
        if not isinstance(record, dict) or set(record) != {'name', 'old', 'new'}:
            raise RecoveryError('Invalid recovery record; no automatic changes.')
        name = record['name']
        if not isinstance(name, str) or name not in names or name in seen:
            raise RecoveryError('Unexpected recovery Skill; no automatic changes.')
        seen.add(name)
        if not isinstance(record['new'], str) or not re.fullmatch('[0-9a-f]{64}', record['new']):
            raise RecoveryError('Invalid new recovery digest.')
        if record['old'] is not None and (not isinstance(record['old'], str) or not re.fullmatch('[0-9a-f]{64}', record['old'])):
            raise RecoveryError('Invalid old recovery digest.')
        target, saved, staged = root / name, backup / name, stage / name
        for candidate in (target, saved, staged):
            reject_link(candidate)
        target_hash = digest(target) if exists(target) else None
        saved_hash = digest(saved) if exists(saved) else None
        staged_hash = digest(staged) if exists(staged) else None
        # Validate the whole plan before moving anything. A user's edits always win.
        if staged_hash not in (None, record['new']):
            raise RecoveryError(f'Staged recovery data changed; preserve for manual review: {staged}')
        if exists(saved):
            if saved_hash != record['old'] or record['old'] is None or target_hash not in (None, record['new']):
                raise RecoveryError(f'Recovery data changed; preserve for manual review: {target}')
            if target_hash is not None and staged_hash is not None:
                raise RecoveryError(f'Ambiguous duplicate recovery data: {target}')
        elif target_hash != record['old']:
            if record['old'] is not None or target_hash != record['new'] or staged_hash is not None:
                raise RecoveryError(f'Original recovery data missing or changed: {target}')
    if seen != names:
        raise RecoveryError('Recovery journal must identify the complete Skill pair.')
    for record in records:
        name = record['name']
        target, saved = root / name, backup / name
        if exists(saved) or record['old'] is None:
            if exists(target):
                stage.mkdir(exist_ok=True)
                os.replace(target, stage / name)
            if exists(saved):
                os.replace(saved, target)
    # All original trees are restored. Remaining files are retained unless exactly known.
    path.unlink()
    if stage.is_dir():
        for record in records:
            staged = stage / record['name']
            if exists(staged):
                shutil.rmtree(staged)
        if not any(stage.iterdir()):
            stage.rmdir()
    if backup.is_dir() and not any(backup.iterdir()):
        backup.rmdir()
    return True
