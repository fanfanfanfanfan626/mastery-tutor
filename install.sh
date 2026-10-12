#!/bin/sh
set -eu

CHECK_ONLY=0
USE_CLI_INSTALL=0
CODEX_COMMAND=codex
CLI_DOCUMENTATION_URL=https://learn.chatgpt.com/docs/codex/cli

emit_cli_blocker() {
    candidate=$1
    detail=$2
    case "$candidate" in
        *WindowsApps*)
            candidate_note="The discovered executable is inside WindowsApps. Treat it as an unavailable app-internal candidate; do not copy it or change package permissions."
            ;;
        *)
            candidate_note="The requested Codex command is missing or could not be launched from this task."
            ;;
    esac
    {
        echo "MASTERY_INSTALL_STATUS=blocked"
        echo "MASTERY_BLOCKER=codex-cli-unavailable"
        echo "MASTERY_CLI_CANDIDATE=$candidate"
        echo "MASTERY_RECOVERY=official-cli"
        echo "MASTERY_CLI_DOCS=$CLI_DOCUMENTATION_URL"
        echo
        echo "$candidate_note"
        echo "$detail"
        echo
        echo "The repository passed preflight, but the plugin is not installed and no Codex configuration was changed."
        echo "Follow AI_INSTALL.md's controlled recovery using current official OpenAI CLI documentation, then rerun this installer."
        echo "Do not use skill-installer, copy a nested Skill, copy an executable out of WindowsApps, or change WindowsApps permissions."
    } >&2
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --check-only)
            CHECK_ONLY=1
            shift
            ;;
        --use-cli-install)
            USE_CLI_INSTALL=1
            shift
            ;;
        --codex)
            if [ "$#" -lt 2 ]; then
                echo "--codex requires a command path" >&2
                exit 2
            fi
            CODEX_COMMAND=$2
            shift 2
            ;;
        *)
            echo "Unknown argument: $1" >&2
            exit 2
            ;;
    esac
done

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPOSITORY_ROOT=$SCRIPT_DIR
MARKETPLACE_PATH=$REPOSITORY_ROOT/.agents/plugins/marketplace.json
PLUGIN_MANIFEST_PATH=$REPOSITORY_ROOT/plugins/mastery-tutor/.codex-plugin/plugin.json
VERSION_PATH=$REPOSITORY_ROOT/VERSION

if [ ! -f "$MARKETPLACE_PATH" ]; then
    echo "Not a Mastery Tutor marketplace root: missing .agents/plugins/marketplace.json" >&2
    exit 1
fi
if [ ! -f "$PLUGIN_MANIFEST_PATH" ]; then
    echo "Incomplete plugin package: missing plugins/mastery-tutor/.codex-plugin/plugin.json" >&2
    exit 1
fi
if [ ! -f "$VERSION_PATH" ]; then
    echo "Incomplete plugin package: missing VERSION" >&2
    exit 1
fi
if ! grep -Eq '"name"[[:space:]]*:[[:space:]]*"mastery-tutor"' "$MARKETPLACE_PATH"; then
    echo "Marketplace identity mismatch: expected mastery-tutor" >&2
    exit 1
fi
if ! grep -Eq '"path"[[:space:]]*:[[:space:]]*"\./plugins/mastery-tutor"' "$MARKETPLACE_PATH"; then
    echo "Marketplace source mismatch: expected local path ./plugins/mastery-tutor" >&2
    exit 1
fi
if ! grep -Eq '"name"[[:space:]]*:[[:space:]]*"mastery-tutor"' "$PLUGIN_MANIFEST_PATH"; then
    echo "Plugin identity mismatch: expected mastery-tutor" >&2
    exit 1
fi
if ! grep -Eq '"skills"[[:space:]]*:[[:space:]]*"\./skills/"' "$PLUGIN_MANIFEST_PATH"; then
    echo "Plugin identity mismatch: expected bundled ./skills/" >&2
    exit 1
fi
RELEASE_VERSION=$(tr -d '\r\n' < "$VERSION_PATH")
if ! grep -Eq '"version"[[:space:]]*:[[:space:]]*"'"$RELEASE_VERSION"'"' "$PLUGIN_MANIFEST_PATH"; then
    echo "Plugin version mismatch: generated adapter does not match VERSION" >&2
    exit 1
fi
for skill in mastery-coach mastery-tool-creator; do
    if [ ! -f "$REPOSITORY_ROOT/plugins/mastery-tutor/skills/$skill/SKILL.md" ]; then
        echo "Incomplete plugin package: missing bundled Skill $skill/SKILL.md" >&2
        exit 1
    fi
done

echo "Preflight passed: Mastery Tutor $RELEASE_VERSION with both bundled Skills."
echo "Repository root: $REPOSITORY_ROOT"

if [ "$CHECK_ONLY" -eq 1 ]; then
    echo "Check-only mode: Codex configuration was not changed."
    exit 0
fi

case "$REPOSITORY_ROOT/" in
    "${TMPDIR:-/tmp}/"*|/tmp/*|/var/tmp/*)
        echo "Refusing a temporary install source. Move the complete repository to a stable directory and run again." >&2
        exit 1
        ;;
esac

MASTERY_CODEX_HOME=${CODEX_HOME:-"$HOME/.codex"}
LEGACY_SKILLS=""
for skill in mastery-coach mastery-tool-creator; do
    path=$MASTERY_CODEX_HOME/skills/$skill
    if [ -d "$path" ]; then
        LEGACY_SKILLS="${LEGACY_SKILLS}${path}
"
    fi
done

if [ -n "$LEGACY_SKILLS" ]; then
    echo "Legacy standalone Mastery Skills were found:" >&2
    printf '%s' "$LEGACY_SKILLS" >&2
    echo >&2
    echo "No Codex configuration was changed. Show these paths to the user and ask before removing or moving them." >&2
    echo "Do not delete them silently and do not install around them." >&2
    exit 1
fi

if ! command -v "$CODEX_COMMAND" >/dev/null 2>&1; then
    emit_cli_blocker "$CODEX_COMMAND" "The Codex CLI command could not be found."
    exit 1
fi
if ! CODEX_VERSION=$("$CODEX_COMMAND" --version 2>&1); then
    CODEX_CANDIDATE=$(command -v "$CODEX_COMMAND" 2>/dev/null || printf '%s' "$CODEX_COMMAND")
    emit_cli_blocker "$CODEX_CANDIDATE" "The Codex CLI probe failed."
    exit 1
fi
echo "Codex CLI: $CODEX_VERSION"

if ! EXISTING_PLUGIN_LIST=$("$CODEX_COMMAND" plugin list 2>&1); then
    echo "Could not inspect existing Codex plugins before installation. No plugin changes were made." >&2
    exit 1
fi
case "$EXISTING_PLUGIN_LIST" in
    *mastery-learning*)
        echo "MASTERY_INSTALL_STATUS=blocked" >&2
        echo "MASTERY_BLOCKER=legacy-plugin-installed" >&2
        echo "The old 'mastery-learning' Codex plugin is still installed. It was not removed." >&2
        echo "Follow MIGRATION.md, preserve every .mastery learner workspace, remove only the old plugin identity, and rerun this installer." >&2
        exit 1
        ;;
esac

read_marketplace_source() {
    "$CODEX_COMMAND" plugin marketplace list > "$MASTERY_LIST_TEMP" || return 1
    awk '$1 == "mastery-tutor" { sub(/^[[:space:]]*mastery-tutor[[:space:]]+/, ""); sub(/[[:space:]]+$/, ""); print; exit }' "$MASTERY_LIST_TEMP"
}
MASTERY_LIST_TEMP=$(mktemp)
trap 'rm -f "$MASTERY_LIST_TEMP"' EXIT HUP INT TERM
SOURCE=$(read_marketplace_source) || { echo 'Could not inspect marketplace sources.' >&2; exit 1; }
if [ -n "$SOURCE" ] && [ "$SOURCE" != "$REPOSITORY_ROOT" ]; then
    echo "MASTERY_BLOCKER=marketplace-source-conflict" >&2
    printf 'Registered: %s\nRequested: %s\nNo source was replaced. Ask the user which source to keep.\n' "$SOURCE" "$REPOSITORY_ROOT" >&2
    exit 1
fi
if [ -z "$SOURCE" ]; then
    "$CODEX_COMMAND" plugin marketplace add "$REPOSITORY_ROOT" || exit 1
    SOURCE=$(read_marketplace_source) || exit 1
    if [ "$SOURCE" != "$REPOSITORY_ROOT" ]; then
        echo 'Registration may be present, but exact-source verification failed. Inspect codex plugin marketplace list before retrying. No plugin installation was attempted.' >&2
        exit 1
    fi
fi
OBSERVED=$("$CODEX_COMMAND" plugin list --marketplace mastery-tutor) || exit 1
if printf '%s\n' "$OBSERVED" | grep -Eq '^[[:space:]]*mastery-tutor@mastery-tutor[[:space:]]+installed,[[:space:]]*enabled([[:space:]]|$)'; then
    echo 'MASTERY_INSTALL_STATUS=installed'
    echo 'Installed and enabled. No configuration change needed. Open a new Codex task.'
    exit 0
fi
if [ "$USE_CLI_INSTALL" -ne 1 ]; then
    echo 'MASTERY_INSTALL_STATUS=registered-awaiting-ui-install'
    echo 'Open the desktop Plugins Directory, install and enable Mastery Tutor from its marketplace, then rerun this script to verify. Registration is not installation.'
    echo 'Official flow: https://developers.openai.com/plugins/build/plugins'
    echo 'If explicitly requested and supported by this CLI, --use-cli-install enables the compatibility installation path.'
    exit 2
fi
ADD_HELP=$("$CODEX_COMMAND" plugin add --help) || exit 1
printf '%s\n' "$ADD_HELP" | grep -Fq 'Usage: codex plugin add' || { echo 'Use the Plugins Directory; this CLI has no compatible plugin add command.' >&2; exit 1; }
if ! "$CODEX_COMMAND" plugin add "mastery-tutor@mastery-tutor"; then
    echo "Codex plugin installation failed. Do not copy a nested Skill as a fallback." >&2
    exit 1
fi

if ! PLUGIN_LIST=$("$CODEX_COMMAND" plugin list --marketplace mastery-tutor 2>&1); then
    echo "The plugin command completed, but 'codex plugin list' failed." >&2
    exit 1
fi
if ! printf '%s\n' "$PLUGIN_LIST" | grep -Eq '^[[:space:]]*mastery-tutor@mastery-tutor[[:space:]]+installed,[[:space:]]*enabled([[:space:]]|$)'; then
        echo "Installation verification failed: 'codex plugin list' did not contain mastery-tutor." >&2
        exit 1
fi
printf '%s\n' "$PLUGIN_LIST"
echo 'MASTERY_INSTALL_STATUS=installed'
echo "Installed and verified mastery-tutor as a complete Codex plugin. Open a new Codex task to load both bundled Skills."
