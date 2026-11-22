<#!
.SYNOPSIS
  Run the existing isolated Windows OCR benchmark, then start PRIVATE manual labels.
.DESCRIPTION
  Default: delegate to V1.1c one-command pinned benchmark and open a Tkinter
  still-image annotator. -BenchOnly avoids the UI. -LabelsOnly reuses cached
  venv/reference with no Python package, model or network installation.
  No game/process manipulation or automatic capture. No uploads.
!#>
[CmdletBinding()]
param(
    [switch]$Offline,
    [switch]$LabelsOnly,
    [switch]$BenchOnly,
    [string]$OutputRoot = (Join-Path $env:LOCALAPPDATA "ARAMOracle\OCR-V11c"),
    [string]$TesseractExe = ""
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($LabelsOnly -and $BenchOnly) {
    throw "-LabelsOnly and -BenchOnly cannot be combined."
}
$Repository = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$PrivateRoot = [IO.Path]::GetFullPath($OutputRoot)
$VenvPython = Join-Path $PrivateRoot "venv\Scripts\python.exe"
$Reference = Join-Path $PrivateRoot "reference"
$ReferenceSha = "7624b27c1d025c4183c2a78aa11609dda45ecf71"

# Reuse V1.1c rather than duplicating setup, pin checks, baseline tests
# and cold-start performance measurement.
if (-not $LabelsOnly) {
    # PowerShell script commands require named hashtable splatting. An array
    # of "-Parameter", "value" elements binds as positional arguments in 5.1.
    $benchmarkParams = @{ OutputRoot = $PrivateRoot }
    if ($Offline) { $benchmarkParams.Offline = $true }
    if ($TesseractExe) { $benchmarkParams.TesseractExe = $TesseractExe }
    & (Join-Path $Repository "benchmarks\ocr_v11c\Run-OCRBenchmark.ps1") @benchmarkParams
    if ($LASTEXITCODE -ne 0) {
        throw "V1.1c benchmark failed. Labeler not started."
    }
}
if ($BenchOnly) {
    Write-Host "Benchmark finished. Any results are LOCAL to this computer."
    exit 0
}
if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
    throw "Isolated Python 3.11 environment missing. Run without -LabelsOnly first."
}
if (-not (Test-Path -LiteralPath $Reference -PathType Container)) {
    throw "Pinned reference missing. Run without -LabelsOnly first."
}
$head = (& git -C $Reference rev-parse HEAD)
if ($LASTEXITCODE -ne 0 -or $head.Trim() -ne $ReferenceSha) {
    throw "Pinned reference differs from audited SHA; do not label."
}
& $VenvPython -c "import tkinter; import PIL.ImageTk; print('LOCAL_GUI_DEPENDENCIES_OK')"
if ($LASTEXITCODE -ne 0) {
    throw "Tkinter/Pillow are missing from isolated Python. Install the full python.org Python 3.11 (including Tcl/Tk)."
}
Push-Location $Repository
try {
    Write-Host "Launching PRIVATE manual labeler. Only local still screenshots; no OCR unless explicitly requested."
    & $VenvPython -m benchmarks.ocr_v11d.label_ui --private-root (Join-Path $PrivateRoot "private-captures") --reference $Reference
    if ($LASTEXITCODE -ne 0) { throw "Local labeler exited with an error." }
} finally {
    Pop-Location
}
