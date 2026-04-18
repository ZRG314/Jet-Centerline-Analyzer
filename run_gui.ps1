param(
    # Optional override, e.g. -Python "C:\Python314\python.exe" or -Python "py"
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvDir = Join-Path $Root ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$Requirements = Join-Path $Root "requirements.txt"
$GuiEntrypoint = Join-Path $Root "Code\gui.py"

function Resolve-Python {
    param([string]$PythonArg)

    if ($PythonArg.Trim().Length -gt 0) {
        $exe = $PythonArg.Trim()
        $preArgs = @()
        if ($exe -ieq "py" -or $exe -ieq "py.exe") {
            $preArgs = @("-3.14")
        }

        return @{
            Exe     = $exe
            PreArgs = $preArgs
        }
    }

    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($null -ne $py) {
        return @{
            Exe     = "py"
            PreArgs = @("-3.14")
        }
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($null -ne $python) {
        return @{
            Exe     = "python"
            PreArgs = @()
        }
    }

    throw "Neither 'py' nor 'python' was found on PATH. Install Python 3.14+ and try again."
}

$PythonCmd = Resolve-Python -PythonArg $Python

if (-not (Test-Path -LiteralPath $VenvPython)) {
    $pretty = ($PythonCmd.Exe + " " + ($PythonCmd.PreArgs -join " ")).Trim()
    Write-Host "Creating venv at $VenvDir using: $pretty"
    & $PythonCmd.Exe @($PythonCmd.PreArgs) -m venv $VenvDir
}

if (-not (Test-Path -LiteralPath $VenvPython)) {
    throw "venv python was not found at $VenvPython"
}

Write-Host "Upgrading pip..."
& $VenvPython -m pip install --upgrade pip | Out-Host

Write-Host "Installing requirements from $Requirements..."
& $VenvPython -m pip install -r $Requirements | Out-Host

Write-Host "Launching GUI..."
& $VenvPython $GuiEntrypoint
