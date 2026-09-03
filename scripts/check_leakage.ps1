# Data-leakage regression tests (manual run; the pre-push hook runs the same set).
#
#   powershell -File scripts/check_leakage.ps1
#
# Covers backend/tests/test_label_shuffle.py (shuffled-label null test),
# test_split.py (dedup + group split) and test_timestamps.py.
#
# Keep this file ASCII-only: Windows PowerShell 5.1 parses .ps1 with the ANSI
# codepage, not UTF-8, so non-ASCII characters here become a parser error.
$ErrorActionPreference = "Stop"

$backend = Resolve-Path (Join-Path $PSScriptRoot "..\backend")
$python = Join-Path $backend ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }

Push-Location $backend
try {
    & $python -m pytest -m leakage --quiet
    $code = $LASTEXITCODE
}
finally {
    Pop-Location
}

if ($code -ne 0) {
    Write-Host ""
    Write-Host "Leakage tests FAILED - find out why, do not bypass." -ForegroundColor Red
}
exit $code
