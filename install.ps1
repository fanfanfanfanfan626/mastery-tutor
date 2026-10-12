[CmdletBinding()]
param(
    [switch]$CheckOnly,
    [switch]$UseCliInstall,
    [string]$CodexCommand = "codex"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$CliDocumentationUrl = "https://learn.chatgpt.com/docs/codex/cli"

function Get-CodexCandidate {
    param([string]$Command)

    try {
        $CommandInfo = Get-Command -Name $Command -ErrorAction Stop | Select-Object -First 1
        $Candidate = [string]$CommandInfo.Source
        if ([string]::IsNullOrWhiteSpace($Candidate)) {
            $Candidate = [string]$CommandInfo.Definition
        }
        if (-not [string]::IsNullOrWhiteSpace($Candidate)) {
            return $Candidate
        }
    } catch {
        # The structured blocker below still reports the requested command.
    }
    return $Command
}

function New-CliBlockerMessage {
    param(
        [string]$Command,
        [string]$Detail
    )

    $Candidate = Get-CodexCandidate -Command $Command
    $CandidateNote = if ($Candidate -match '(?i)[\\/]WindowsApps[\\/]') {
        "The discovered executable is inside WindowsApps. Treat it as an unavailable app-internal candidate; do not copy it or change package permissions."
    } else {
        "The requested Codex command is missing or could not be launched from this task."
    }

    return @"
MASTERY_INSTALL_STATUS=blocked
MASTERY_BLOCKER=codex-cli-unavailable
MASTERY_CLI_CANDIDATE=$Candidate
MASTERY_RECOVERY=official-cli
MASTERY_CLI_DOCS=$CliDocumentationUrl

$CandidateNote
$Detail

The repository passed preflight, but the plugin is not installed and no Codex configuration was
changed. Follow AI_INSTALL.md's controlled recovery using current official OpenAI CLI documentation,
then rerun this installer. Do not use skill-installer, copy a nested Skill, copy an executable out
of WindowsApps, or change WindowsApps permissions.
"@
}

function Invoke-CodexCapture {
    param(
        [string]$Command,
        [string[]]$Arguments
    )

    try {
        $CommandInfo = Get-Command -Name $Command -ErrorAction Stop | Select-Object -First 1
    } catch {
        throw "Codex CLI launch failed: $($_.Exception.Message)"
    }

    $PreviousErrorActionPreference = $ErrorActionPreference
    try {
        # Native programs may emit advisory stderr while still succeeding. Windows PowerShell
        # turns redirected native stderr into ErrorRecord objects and, under the script-wide
        # Stop policy, would otherwise throw before LASTEXITCODE can be checked.
        $ErrorActionPreference = "Continue"
        $Output = @(& $CommandInfo @Arguments 2>&1)
        $ExitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $PreviousErrorActionPreference
    }

    return [pscustomobject]@{
        ExitCode = $ExitCode
        Output = @($Output | ForEach-Object { [string]$_ })
    }
}

$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot ".")).Path
$MarketplacePath = Join-Path $RepositoryRoot ".agents\plugins\marketplace.json"
$PluginManifestPath = Join-Path $RepositoryRoot "plugins\mastery-tutor\.codex-plugin\plugin.json"
$VersionPath = Join-Path $RepositoryRoot "VERSION"

if (-not (Test-Path -LiteralPath $MarketplacePath -PathType Leaf)) {
    throw "Not a Mastery Tutor marketplace root: missing .agents/plugins/marketplace.json"
}
if (-not (Test-Path -LiteralPath $PluginManifestPath -PathType Leaf)) {
    throw "Incomplete plugin package: missing plugins/mastery-tutor/.codex-plugin/plugin.json"
}
if (-not (Test-Path -LiteralPath $VersionPath -PathType Leaf)) {
    throw "Incomplete plugin package: missing VERSION"
}

$Marketplace = Get-Content -Raw -LiteralPath $MarketplacePath | ConvertFrom-Json
$PluginManifest = Get-Content -Raw -LiteralPath $PluginManifestPath | ConvertFrom-Json
$ReleaseVersion = (Get-Content -Raw -LiteralPath $VersionPath).Trim()
$MarketplacePlugin = @(@($Marketplace.plugins) | Where-Object { $_.name -eq "mastery-tutor" })

if ($Marketplace.name -ne "mastery-tutor" -or $MarketplacePlugin.Count -ne 1) {
    throw "Marketplace identity mismatch: expected exactly one mastery-tutor entry"
}
if ($MarketplacePlugin[0].source.source -ne "local" -or $MarketplacePlugin[0].source.path -ne "./plugins/mastery-tutor") {
    throw "Marketplace source mismatch: expected local path ./plugins/mastery-tutor"
}
if ($PluginManifest.name -ne "mastery-tutor" -or $PluginManifest.skills -ne "./skills/") {
    throw "Plugin identity mismatch: expected mastery-tutor with bundled ./skills/"
}
if ($PluginManifest.version -ne $ReleaseVersion) {
    throw "Plugin version mismatch: generated adapter does not match VERSION"
}
$BundledSkillsRoot = Join-Path $RepositoryRoot 'plugins\mastery-tutor\skills'
foreach ($SkillName in @('mastery-coach', 'mastery-tool-creator')) {
    $SkillManifest = Join-Path (Join-Path $BundledSkillsRoot $SkillName) 'SKILL.md'
    if (-not (Test-Path -LiteralPath $SkillManifest -PathType Leaf)) {
        throw "Incomplete plugin package: missing bundled Skill $SkillName/SKILL.md"
    }
}

Write-Output "Preflight passed: Mastery Tutor $ReleaseVersion with both bundled Skills."
Write-Output "Repository root: $RepositoryRoot"

if ($CheckOnly) {
    Write-Output "Check-only mode: Codex configuration was not changed."
    exit 0
}

$TemporaryRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath()).TrimEnd('\')
if ($RepositoryRoot.StartsWith($TemporaryRoot + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing a temporary install source. Move the complete repository to a stable directory and run again."
}

$CodexHome = if ($env:CODEX_HOME) {
    [System.IO.Path]::GetFullPath($env:CODEX_HOME)
} else {
    Join-Path ([Environment]::GetFolderPath('UserProfile')) '.codex'
}
$StandaloneSkillsRoot = Join-Path $CodexHome 'skills'
$LegacySkills = @(
    @(
        'mastery-coach',
        'mastery-tool-creator'
    ) | ForEach-Object {
        Join-Path $StandaloneSkillsRoot $_
    } | Where-Object {
        Test-Path -LiteralPath $_ -PathType Container
    }
)

if ($LegacySkills.Count -gt 0) {
    $LegacyList = $LegacySkills -join [Environment]::NewLine
    throw @"
Legacy standalone Mastery Skills were found:
$LegacyList

No Codex configuration was changed. These copies can shadow the complete plugin. Show the paths to
the user and ask before removing or moving them, then rerun this installer. Do not delete them
silently and do not install around them.
"@
}

try {
    $CodexVersionResult = Invoke-CodexCapture -Command $CodexCommand -Arguments @("--version")
} catch {
    $CliBlockerMessage = New-CliBlockerMessage -Command $CodexCommand -Detail "Codex CLI launch failed: $($_.Exception.Message)"
    [Console]::Error.WriteLine($CliBlockerMessage)
    exit 1
}
if ($CodexVersionResult.ExitCode -ne 0) {
    $CliBlockerMessage = New-CliBlockerMessage -Command $CodexCommand -Detail "Codex CLI probe failed with exit code $($CodexVersionResult.ExitCode)."
    [Console]::Error.WriteLine($CliBlockerMessage)
    exit 1
}
$CodexVersion = $CodexVersionResult.Output
Write-Output "Codex CLI: $($CodexVersion -join ' ')"

try {
    $ExistingPluginListResult = Invoke-CodexCapture -Command $CodexCommand -Arguments @("plugin", "list")
} catch {
    throw "Could not inspect existing Codex plugins before installation. No plugin changes were made. $($_.Exception.Message)"
}
if ($ExistingPluginListResult.ExitCode -ne 0) {
    throw "Could not inspect existing Codex plugins before installation. No plugin changes were made."
}
$ExistingPluginList = $ExistingPluginListResult.Output
$ExistingPluginListText = $ExistingPluginList -join [Environment]::NewLine
if ($ExistingPluginListText -match '(?im)^\s*mastery-learning(?:@\S+)?\s+') {
    throw @"
MASTERY_INSTALL_STATUS=blocked
MASTERY_BLOCKER=legacy-plugin-installed

The old 'mastery-learning' Codex plugin is still installed. It was not removed. Follow MIGRATION.md,
confirm that learner workspaces remain intact, remove only the old plugin identity, then rerun this
installer. Never delete .mastery learner data during the product rename.
"@
}

function Read-MarketplaceSource {
    $Result = Invoke-CodexCapture -Command $CodexCommand -Arguments @('plugin', 'marketplace', 'list')
    if ($Result.ExitCode -ne 0) { throw 'Could not inspect marketplace sources. No source was replaced.' }
    foreach ($Line in $Result.Output) {
        if ($Line -match '^\s*mastery-tutor\s+(.+?)\s*$') { return $Matches[1] }
    }
    return $null
}

$Source = Read-MarketplaceSource
if ($Source) {
    if (-not [string]::Equals([IO.Path]::GetFullPath($Source).TrimEnd('\','/'), $RepositoryRoot.TrimEnd('\','/'), [StringComparison]::OrdinalIgnoreCase)) {
        throw "MASTERY_BLOCKER=marketplace-source-conflict`nRegistered: $Source`nRequested: $RepositoryRoot`nNo source was replaced. Ask the user which source to keep."
    }
} else {
    $Added = Invoke-CodexCapture -Command $CodexCommand -Arguments @('plugin', 'marketplace', 'add', $RepositoryRoot)
    if ($Added.ExitCode -ne 0) { throw 'Marketplace registration failed; the plugin was not installed.' }
    $Source = Read-MarketplaceSource
    if (-not $Source -or -not [string]::Equals([IO.Path]::GetFullPath($Source).TrimEnd('\','/'), $RepositoryRoot.TrimEnd('\','/'), [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Registration may be present, but exact-source verification failed. Inspect codex plugin marketplace list before retrying. No plugin installation was attempted.'
    }
}

$Observed = Invoke-CodexCapture -Command $CodexCommand -Arguments @('plugin', 'list', '--marketplace', 'mastery-tutor')
if ($Observed.ExitCode -ne 0) { throw 'Marketplace is registered, but installed plugin state could not be inspected.' }
if (($Observed.Output -join "`n") -match '(?im)^\s*mastery-tutor@mastery-tutor\s+installed,\s*enabled(?:\s|$)') {
    Write-Output 'MASTERY_INSTALL_STATUS=installed'
    Write-Output 'Installed and enabled. No configuration change needed. Open a new Codex task.'
    exit 0
}
if (-not $UseCliInstall) {
    Write-Output 'MASTERY_INSTALL_STATUS=registered-awaiting-ui-install'
    Write-Output 'Open the desktop Plugins Directory, install and enable Mastery Tutor from its marketplace, then rerun this script to verify. Registration is not installation.'
    Write-Output 'Official flow: https://developers.openai.com/plugins/build/plugins'
    Write-Output 'If explicitly requested and supported by this CLI, -UseCliInstall enables the compatibility installation path.'
    exit 2
}
$AddHelp = Invoke-CodexCapture -Command $CodexCommand -Arguments @('plugin', 'add', '--help')
if ($AddHelp.ExitCode -ne 0 -or ($AddHelp.Output -join "`n") -notmatch 'Usage:\s+codex plugin add') {
    throw 'Compatibility plugin add command unavailable. Use the Plugins Directory. Marketplace remains registered.'
}

try {
    $PluginAddResult = Invoke-CodexCapture -Command $CodexCommand -Arguments @("plugin", "add", "mastery-tutor@mastery-tutor")
} catch {
    throw "Could not launch the Codex CLI for plugin installation. Do not copy a nested Skill as a fallback. $($_.Exception.Message)"
}
$PluginAddResult.Output | Write-Output
if ($PluginAddResult.ExitCode -ne 0) {
    throw "Codex plugin installation failed with exit code $($PluginAddResult.ExitCode)."
}

try {
    $PluginListResult = Invoke-CodexCapture -Command $CodexCommand -Arguments @("plugin", "list", "--marketplace", "mastery-tutor")
} catch {
    throw "The plugin command completed, but installation verification could not run. $($_.Exception.Message)"
}
if ($PluginListResult.ExitCode -ne 0) {
    throw "The plugin command completed, but 'codex plugin list' failed with exit code $($PluginListResult.ExitCode)."
}
$PluginList = $PluginListResult.Output
$PluginListText = $PluginList -join [Environment]::NewLine
if ($PluginListText -notmatch '(?im)^\s*mastery-tutor@mastery-tutor\s+installed,\s*enabled(?:\s|$)') {
    throw "Installation verification failed: 'codex plugin list' did not contain mastery-tutor."
}

Write-Output $PluginListText
Write-Output 'MASTERY_INSTALL_STATUS=installed'
Write-Output "Installed and verified mastery-tutor as a complete Codex plugin. Open a new Codex task to load both bundled Skills."
