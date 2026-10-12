# Maintainer navigation

Mastery Tutor is a local-first teaching bundle with two canonical Skills. Stable host behavior
and learning efficacy are separate from deterministic engineering tests; see [COMPATIBILITY.md](COMPATIBILITY.md).

| Work | Source of truth | Smallest checks |
|---|---|---|
| Portable installation and restart recovery | `install-agent-skills.py`, `install_transaction.py`, `INSTALL.md` | `python -m unittest discover -s quality -p "test_install_recovery.py"`; `test_agent_skill_distribution.py` |
| Codex registration and generated adapter | `install.ps1`, `install.sh`, `adapters/codex/`, `AGENTS.md` | `quality/build_adapters.py --check`; `test_install_contract.py`, `test_install_states.py` |
| Prepared browser sample (not live AI) | `docs/demo.html`, `docs/demo.en.html`, `docs/assets/demo*.js` | `node quality/test_demo.cjs`; `node quality/test_demo_ui.cjs`; browser keyboard flow |
| Learning state and privacy | `skills/mastery-coach/scripts/`, `skills/mastery-coach/references/` | `quality/test_state_regressions_v4.py`, `quality/test_system.py` |
| Teaching artifacts | `skills/mastery-tool-creator/` | `quality/test_tool_contract_v4.py` |
| Immutable packages and release gates | `VERSION`, `quality/build_release.py`, `quality/release_audit.py`, `.github/workflows/` | full `quality/test_*.py`; three-OS reproducibility; stable E2 gate |

Run tests from the repository root. Python 3.10+ and Node 22 (browser sample tests) are sufficient;
no hosted account is required for the prepared demo. Never commit learner workspaces, credentials,
or local installation artifacts. Generated adapters are not independent editable sources.

Operating boundaries: [SUPPORT.md](SUPPORT.md), [SECURITY.md](SECURITY.md), [MIGRATION.md](MIGRATION.md).
Rollback a repository update by reverting its PR; do not rewrite published release tags. Portable
replacement preserves a backup, and interrupted recovery never substitutes for checking a named
host. A running host may observe a partial pair; close it before installation. Existing learner
records are outside the installer's write scope. The repository owner handles Issues; no continuous
operator or response-time promise is implied.
