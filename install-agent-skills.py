#!/usr/bin/env python3
"""Install the canonical Mastery Tutor Skill bundle into compatible AI hosts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import uuid
from pathlib import Path
from typing import Any

from install_transaction import JOURNAL, LOCK, InstallBusyError, RecoveryError, exists, installation_lock, recover, transaction_paths, write_journal


ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = ROOT / "agent-skill-set.json"
IGNORED_NAMES = {"__pycache__", ".pytest_cache", ".mypy_cache", ".DS_Store"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}
HOST_DIRECTORIES = {
    "agent-skills": {"user": Path(".agents/skills"), "project": Path(".agents/skills")},
    "claude-code": {"user": Path(".claude/skills"), "project": Path(".claude/skills")},
    "github-copilot": {"user": Path(".copilot/skills"), "project": Path(".agents/skills")},
}


def is_reparse_point(path: Path) -> bool:
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except OSError:
        return False
    return path.is_symlink() or bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def load_manifest() -> dict[str, Any]:
    try:
        value = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"Cannot read agent-skill-set.json: {error}") from error
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise SystemExit("agent-skill-set.json must use schema_version 1")
    if value.get("version_source") != "VERSION":
        raise SystemExit("agent-skill-set.json must read its version from VERSION")
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    parts = version.split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise SystemExit("VERSION must contain one numeric semantic version")
    value["version"] = version
    skills = value.get("skills")
    if not isinstance(skills, list) or not skills:
        raise SystemExit("agent-skill-set.json must declare at least one Skill")
    return value


def skill_frontmatter_name(path: Path) -> str:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise SystemExit(f"Cannot read {path}: {error}") from error
    if not lines or lines[0].strip() != "---":
        raise SystemExit(f"Skill is missing YAML frontmatter: {path}")
    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip().strip("\"'")
    if not fields.get("name") or not fields.get("description"):
        raise SystemExit(f"Skill frontmatter requires name and description: {path}")
    return fields["name"]


def source_skills(manifest: dict[str, Any]) -> list[tuple[str, Path]]:
    result: list[tuple[str, Path]] = []
    names: set[str] = set()
    for entry in manifest["skills"]:
        if not isinstance(entry, dict) or entry.get("required") is not True:
            raise SystemExit("Every distributed Skill must be a required object")
        name = entry.get("name")
        source_value = entry.get("source")
        if not isinstance(name, str) or not name or name in names or not isinstance(source_value, str):
            raise SystemExit("Skill names and sources must be unique non-empty strings")
        source = (ROOT / source_value).resolve()
        try:
            source.relative_to(ROOT.resolve())
        except ValueError as error:
            raise SystemExit(f"Skill source escapes the repository: {source_value}") from error
        if not source.is_dir() or is_reparse_point(source):
            raise SystemExit(f"Skill source is missing or linked: {source}")
        declared = skill_frontmatter_name(source / "SKILL.md")
        if declared != name or source.name != name:
            raise SystemExit(f"Skill identity mismatch for {source}: manifest={name!r}, frontmatter={declared!r}")
        names.add(name)
        result.append((name, source))
    return result


def tree_records(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not root.is_dir() or is_reparse_point(root):
        raise SystemExit(f"Skill tree is missing or linked: {root}")
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root)
        if any(part in IGNORED_NAMES for part in relative.parts) or path.suffix.lower() in IGNORED_SUFFIXES:
            continue
        if is_reparse_point(path):
            raise SystemExit(f"Skill tree contains a symbolic link, junction, or reparse point: {path}")
        if path.is_file():
            data = path.read_bytes()
            records.append({
                "path": relative.as_posix(),
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            })
    if not any(record["path"] == "SKILL.md" for record in records):
        raise SystemExit(f"Skill tree has no SKILL.md: {root}")
    return records


def tree_digest(root: Path) -> str:
    canonical = json.dumps(tree_records(root), separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def resolve_target(args: argparse.Namespace) -> Path:
    if args.target:
        return args.target.expanduser().resolve()
    if args.host == "custom":
        raise SystemExit("--host custom requires --target <absolute-skills-directory>")
    relative = HOST_DIRECTORIES[args.host][args.scope]
    if args.scope == "user":
        return (Path.home() / relative).resolve()
    base = args.project_root.expanduser().resolve() if args.project_root else Path.cwd().resolve()
    return (base / relative).resolve()


def copy_source(source: Path, destination: Path) -> None:
    def ignore(_: str, names: list[str]) -> set[str]:
        return {name for name in names if name in IGNORED_NAMES or Path(name).suffix.lower() in IGNORED_SUFFIXES}

    shutil.copytree(source, destination, symlinks=False, ignore=ignore)


def install_bundle(
    sources: list[tuple[str, Path]], target_root: Path, *, check: bool, replace: bool
) -> dict[str, Any]:
    # Validate source trees before creating even the lock directory. --check is read-only.
    for _, source in sources:
        tree_digest(source)
    try:
        with installation_lock(target_root, create=not check) as locked:
            if check:
                if exists(target_root / JOURNAL):
                    return {'ok': False, 'status': 'recovery-required', 'target': str(target_root),
                            'message': 'Close the host and rerun the install command without --check to recover.'}
                report = _install_bundle(sources, target_root, check=True, replace=False)
                if not locked and (exists(target_root / LOCK) or exists(target_root / JOURNAL)):
                    return {'ok': False, 'status': 'busy', 'target': str(target_root), 'message': 'Installation started during check; retry.'}
                return report
            try:
                recovered = recover(target_root, {name for name, _ in sources}, tree_digest)
            except (RecoveryError, SystemExit, OSError) as error:
                return {'ok': False, 'status': 'recovery-blocked', 'target': str(target_root), 'message': str(error)}
            report = _install_bundle(sources, target_root, check=False, replace=replace)
            if recovered:
                report['recovered_interrupted_install'] = True
            return report
    except InstallBusyError as error:
        return {'ok': False, 'status': 'busy', 'target': str(target_root), 'message': str(error)}


def _install_bundle(
    sources: list[tuple[str, Path]], target_root: Path, *, check: bool, replace: bool
) -> dict[str, Any]:
    expected = {name: tree_digest(source) for name, source in sources}
    existing: dict[str, str | None] = {}
    for name, _ in sources:
        target = target_root / name
        if not exists(target):
            existing[name] = None
        elif not target.is_dir() or is_reparse_point(target):
            existing[name] = "invalid-existing-path"
        else:
            existing[name] = tree_digest(target)

    if check:
        statuses = [
            {
                "name": name,
                "path": str(target_root / name),
                "status": "verified" if existing[name] == expected[name] else "missing-or-different",
                "sha256": existing[name],
                "expected_sha256": expected[name],
            }
            for name, _ in sources
        ]
        return {"ok": all(item["status"] == "verified" for item in statuses), "status": "verified" if all(item["status"] == "verified" for item in statuses) else "not-verified", "target": str(target_root), "skills": statuses}

    if 'invalid-existing-path' in existing.values():
        return {'ok': False, 'status': 'unsafe-target', 'target': str(target_root),
                'message': 'A Skill path is a link or is not a directory; --replace cannot override it.'}

    conflicts = [str(target_root / name) for name, _ in sources if existing[name] not in (None, expected[name])]
    if conflicts and not replace:
        return {"ok": False, "status": "conflict", "target": str(target_root), "conflicts": conflicts, "message": "Existing Skill directories differ. Report them and obtain approval before rerunning with --replace."}
    if all(existing[name] == expected[name] for name, _ in sources):
        return {"ok": True, "status": "already-installed", "target": str(target_root), "skills": [{"name": name, "path": str(target_root / name), "sha256": expected[name]} for name, _ in sources]}

    pending = {name for name, _ in sources if existing[name] != expected[name]}
    target_root.parent.mkdir(parents=True, exist_ok=True)
    target_root.mkdir(parents=True, exist_ok=True)
    identifier = uuid.uuid4().hex
    stage, backup = transaction_paths(target_root, identifier)
    stage.mkdir()
    journal_created = False
    try:
        for name, source in sources:
            if name not in pending:
                continue
            staged = stage / name
            copy_source(source, staged)
            if tree_digest(staged) != expected[name]:
                raise SystemExit(f"Staged Skill bytes differ from source: {name}")
        write_journal(target_root, {'version': 1, 'id': identifier, 'skills': [
            {'name': name, 'old': existing[name], 'new': expected[name]}
            for name, _ in sources
        ]})
        journal_created = True
        for name, _ in sources:
            if name not in pending:
                continue
            target = target_root / name
            if target.exists():
                backup_target = backup / name
                backup.mkdir(parents=True, exist_ok=True)
                os.replace(target, backup_target)
        for name, _ in sources:
            if name not in pending:
                continue
            target = target_root / name
            os.replace(stage / name, target)
        for name, _ in sources:
            if tree_digest(target_root / name) != expected[name]:
                raise SystemExit(f"Installed Skill bytes differ from source: {name}")
        (target_root / JOURNAL).unlink()
    except BaseException:
        if journal_created:
            recover(target_root, {name for name, _ in sources}, tree_digest)
        elif not exists(target_root / JOURNAL):
            shutil.rmtree(stage)
        # A failed rollback leaves its journal and artifacts intact for safe recovery.
        raise
    if stage.is_dir():
        stage.rmdir()

    return {
        "ok": True,
        "status": "installed",
        "target": str(target_root),
        "backup": str(backup) if backup.exists() else None,
        "skills": [{"name": name, "path": str(target_root / name), "sha256": expected[name]} for name, _ in sources],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Install Mastery Tutor into an Agent Skills host")
    parser.add_argument("--host", required=True, choices=[*HOST_DIRECTORIES, "custom"])
    parser.add_argument("--scope", choices=["user", "project"], default="user")
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("--target", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    if args.check and args.replace:
        parser.error("--check and --replace cannot be combined")
    if args.target and not args.target.expanduser().is_absolute():
        parser.error("--target must be an absolute path")
    manifest = load_manifest()
    sources = source_skills(manifest)
    target = resolve_target(args)
    report = install_bundle(sources, target, check=args.check, replace=args.replace)
    report.update({"host": args.host, "scope": args.scope, "skill_set": manifest["name"], "version": manifest["version"]})
    print(json.dumps(report, ensure_ascii=True, indent=2))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
