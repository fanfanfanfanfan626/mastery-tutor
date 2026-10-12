# Engineering preview — E2 pending

This is a testable preview of the Mastery Tutor release candidate, not a stable or behavior-verified release. The latest stable release remains **v0.4.1**, under the former Mastery Learning identity. Do not overwrite learner records during migration.

- `core.zip`: the two cooperating Skills for compatible Agent Skills hosts.
- `codex.zip`: the complete generated Codex plugin and registration instructions.
- `.sha256`: SHA-256 checksums; provenance attestations identify the workflow and source commit.

Read `AI_INSTALL.md` after unpacking. Codex marketplace registration is not the same as installing and enabling a plugin in the app. Other hosts remain experimental or core-compatible; see `COMPATIBILITY.md`.

This preview passes deterministic source checks and tests, archive audits, and Linux/Windows/macOS byte reproducibility. It does **not** satisfy the three-run live-conversation E2 gate required by the stable release workflow, and it does not establish improved learning outcomes.

Try the no-install teaching sample in [English](https://fanfanfanfanfan626.github.io/mastery-tutor/demo.en.html) or [中文](https://fanfanfanfanfan626.github.io/mastery-tutor/demo.html) first. It is a prepared interactive example, not an AI service. Report installation blockers using the [first-use feedback form](https://github.com/fanfanfanfanfan626/mastery-tutor/issues/new?template=first-use.yml). Never upload private learning records or credentials.

Portable installer maintenance: JSON output works with Unicode paths even in legacy consoles.
Interrupted replacements restore the previous pair on retry; conflicting recovery artifacts
are retained for review. Close the host during installation. This is not atomic visibility to a
running host or a power-loss guarantee. See `INSTALL.md` before replacing or removing a pair.

中文：这是工程预览，真实对话验证仍未完成，不替代稳定版。先体验网页样例，再按宿主安装说明试用。请保留所有 `.mastery/` 学习记录；不要把“注册插件源”误认为“已安装并启用插件”。
