# Install or update Throughline on Windows, in PowerShell:
#   irm https://raw.githubusercontent.com/keweijun/throughline/main/install.ps1 | iex
# For the Chinese welcome guide, first run $env:THROUGHLINE_LANGUAGE = 'zh-CN'.
# With options: & ([scriptblock]::Create((irm https://raw.githubusercontent.com/keweijun/throughline/main/install.ps1))) -Language zh-CN -NoOpen
#
# The steps, the same as README "For Codex", install.sh and the one-click updater (#110); change them together:
#   1. install uv if it is missing (uv brings its own Python)
#   2. stop a running Throughline: on Windows it locks its own files
#   3. remove the pre-0.5.1 package name, codex-guided-learning
#   4. install the latest version from main
#   5. run setup: the skill, the course library, the launcher, then open the app
# Courses are never touched. Codex is checked for, not installed.
param([string]$Language = $env:THROUGHLINE_LANGUAGE, [switch]$NoOpen)
# No $ErrorActionPreference = 'Stop': under iex it would stay set in the learner's shell, and in Windows PowerShell 5.1
# it turns uv's progress on stderr into errors. Failures are checked where they matter.
$Package = 'throughline[pdf] @ git+https://github.com/keweijun/throughline'

# 1.
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host 'Installing uv, which installs Throughline and the Python it runs on...'
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}

# 2.
if (Get-Command guided-learning -ErrorAction SilentlyContinue) {
    guided-learning stop
}

# 3. A pipx install, of either name, would clash with uv's guided-learning command.
uv tool uninstall codex-guided-learning *> $null
if (Get-Command pipx -ErrorAction SilentlyContinue) {
    pipx uninstall codex-guided-learning *> $null
    pipx uninstall throughline *> $null
}

# 4.
uv tool install --reinstall-package throughline $Package
if ($LASTEXITCODE -ne 0) { throw 'uv could not install Throughline; see the messages above.' }
uv tool update-shell *> $null  # uv's tool folder on PATH in new terminals
$Bin = (uv tool dir --bin).Trim()

# 5.
$SetupArgs = @('setup')
if ($Language -eq 'zh-CN') { $SetupArgs += '--language', 'zh-CN' }
if ($NoOpen) { $SetupArgs += '--no-open' }
& (Join-Path $Bin 'guided-learning.exe') @SetupArgs
if ($LASTEXITCODE -ne 0) { throw 'Setup did not finish; see the messages above.' }

$CodexApp = Join-Path $env:LOCALAPPDATA 'OpenAI\Codex\bin'
if (-not (Get-Command codex -ErrorAction SilentlyContinue) -and -not (Test-Path $CodexApp)) {
    Write-Host ''
    Write-Host 'Throughline needs Codex to teach, and Codex was not found.'
    Write-Host 'Install Codex (the desktop app or the CLI: https://learn.chatgpt.com/docs/codex/cli), sign in, then open Throughline again.'
}
if (-not (($env:Path -split ';') -contains $Bin)) {
    Write-Host ''
    Write-Host "Open a new terminal to use the throughline command, or run $Bin\throughline.exe now."
}
