# Install Mastery Tutor

Codex: the default installer registers the marketplace, then asks you to install and enable Mastery Tutor in the desktop Plugins Directory. Exit code 2 / `registered-awaiting-ui-install` means this step is still needed. Rerun afterward to verify. Marketplace registration alone is not successful installation. See the [exact Codex workflow](docs/install/codex.md).

Mastery Tutor contains two canonical Agent Skills. Choose the host you are actually using:

| Host | Status | Instructions |
|---|---|---|
| Codex | Engineering-verified; E2 conversation evidence pending | [docs/install/codex.md](docs/install/codex.md) |
| Claude Code | Experimental | [docs/install/claude-code.md](docs/install/claude-code.md) |
| GitHub Copilot | Experimental | [docs/install/github-copilot.md](docs/install/github-copilot.md) |
| OpenCode | Planned | [docs/install/opencode.md](docs/install/opencode.md) |
| Other Agent Skills host | Core only | [docs/install/generic-agent.md](docs/install/generic-agent.md) |

## Ask an AI to install it

Send this message to the AI host you want to use:

```text
请安装 Mastery Tutor：https://github.com/fanfanfanfanfan626/mastery-tutor 。先读取并严格执行仓库根目录的 AI_INSTALL.md，识别当前 AI 宿主并安装完整的两个 Skill；发现旧版本先告诉我，不要直接覆盖或删除任何 .mastery 学习数据。若当前宿主是 Codex 且 codex --version 不可用，我允许你仅按 OpenAI 官方 Codex CLI 文档安装或修复正式 CLI；禁止复制 WindowsApps 内部程序、修改其权限、使用 skill-installer 或拆装嵌套 Skill。完成对应宿主的全部成功条件前不要宣称安装成功。
```

The AI-readable router is [AI_INSTALL.md](AI_INSTALL.md). Package status and feature limits are in
[COMPATIBILITY.md](COMPATIBILITY.md). Existing `mastery-learning` users must read
[MIGRATION.md](MIGRATION.md) before replacing the old Codex plugin identity.

## Portable manual install

Python 3.10 or newer is required for the local state engine and deterministic HTML classroom.

```text
python install-agent-skills.py --host <agent-skills|claude-code|github-copilot> --scope <user|project>
python install-agent-skills.py --host <same-host> --scope <same-scope> --check
```

Use `--project-root <absolute-path>` for another project or `--host custom --target
<absolute-skills-directory>` for a documented compatible host. Existing differing Skill directories
produce a conflict. Use `--replace` only after reviewing the paths; replacement keeps a recoverable
sibling backup.

Close the AI host before installing or replacing the pair. The two directories cannot switch
atomically for a running host. Modifying commands use an advisory lock and a small transaction
journal. After an interrupted replacement, rerun the same installer: it first restores the previous
pair, then evaluates the requested operation. `--check` never repairs files; it reports
`recovery-required` when a journal remains. If recovery finds changed, linked or missing artifacts,
it stops for manual review and retains them. Keep the journal, stage and backup directories in that
case. This is process-interruption recovery, not a guarantee against power loss or filesystem damage.

The retained `.mastery-tutor-install.lock` file is normal and contains no learning data. Do not delete
it while an installer is running. Successful replacement backups are retained for your review.

## Portable removal (manual, host-dependent)

There is no automatic portable uninstall command yet. Close the host and run the matching
`--check` command from the exact release/version that installed this pair. If that release is
unavailable, ownership cannot be verified: stop. If either tree differs or recovery is required,
stop and inspect it first.
For a verified pair, move only the two reported directories (`mastery-coach` and
`mastery-tool-creator`) to a backup outside all Skill discovery directories. Never remove the
parent Skills directory or any `.mastery` workspace. Reopen the host and confirm both Skills are
no longer discovered. Restore the two saved directories to undo removal. Host-specific discovery
and uninstall remain part of the uncompleted compatibility matrix, not a Verified claim.
