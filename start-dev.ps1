param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8000
)

$ErrorActionPreference = 'Stop'
$pythonPath = Join-Path $PSScriptRoot 'venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Backend virtual environment not found. Create venv and install requirements first.'
}

# Local development must serve uploaded media even when .env has DEBUG=False.
$previousDebugValue = [Environment]::GetEnvironmentVariable('DEBUG', 'Process')
Push-Location -LiteralPath $PSScriptRoot
try {
    $env:DEBUG = 'True'
    & $pythonPath manage.py runserver "127.0.0.1:$Port"
}
finally {
    Pop-Location
    [Environment]::SetEnvironmentVariable('DEBUG', $previousDebugValue, 'Process')
}
