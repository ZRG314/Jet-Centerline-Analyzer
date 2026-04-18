param(
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"

$RootScript = Join-Path (Split-Path -Parent $PSScriptRoot) "run_gui.ps1"

if (-not (Test-Path -LiteralPath $RootScript)) {
    throw "Could not find root launcher at $RootScript"
}

& $RootScript -Python $Python
