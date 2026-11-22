<#
.SYNOPSIS
  One-command opt-in ARAM Oracle V1.1c isolated Windows OCR validation.
.DESCRIPTION
  First run provisions a private venv and exact pinned model files outside
  the repository; inference and profiling run offline. -Offline forbids setup
  downloads and requires previously cached artifacts. Never launches League,
  Vanguard, OP.GG, screen capture, or the installed overlay.
#>
[CmdletBinding()]
param(
    [switch]$Offline,
    [switch]$SkipControlled,
    [string]$OutputRoot = (Join-Path $env:LOCALAPPDATA "ARAMOracle\OCR-V11c"),
    [string]$TesseractExe = ""
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$ReferenceSha = "7624b27c1d025c4183c2a78aa11609dda45ecf71"
$V4Sha = "48fc40f24f6d2a207a2b1091d3437eb3cc3eb6b676dc3ef9c37384005483683b"
$V5Sha = "c3461add59bb4323ecba96a492ab75e06dda42467c9e3d0c18db5d1d21924be8"
$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

function Assert-Exit([string]$step) {
    if ($LASTEXITCODE -ne 0) { throw "$step failed (exit $LASTEXITCODE)." }
}
function Invoke-Py311 {
    if ($script:UseLauncher) { & py -3.11 @args }
    else { & python @args }
    Assert-Exit "Python 3.11"
}
function Confirm-Model([string]$path, [string]$expected) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { return $false }
    $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $expected) { throw "Pinned model hash mismatch: $([IO.Path]::GetFileName($path)). Stop." }
    return $true
}

Write-Host "ARAM Oracle V1.1c — isolated offline OCR bench (no game integration)"
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git missing. Install Git for Windows; no global settings will be changed."
}
$script:UseLauncher = [bool](Get-Command py -ErrorAction SilentlyContinue)
if (-not $script:UseLauncher -and -not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python 3.11 is required. Install it and rerun this script."
}
Invoke-Py311 -c 'import sys; assert sys.version_info[:2] == (3,11), "Python 3.11 required"'
$LocalRoot = [IO.Path]::GetFullPath($OutputRoot)
if ($LocalRoot.StartsWith($Repo + [IO.Path]::DirectorySeparatorChar,
                         [StringComparison]::OrdinalIgnoreCase)) {
    throw "OutputRoot must be outside the repository (private data isolation)."
}
New-Item -ItemType Directory -Path $LocalRoot -Force | Out-Null
$Reference = Join-Path $LocalRoot "reference"
$Models = Join-Path $LocalRoot "models"
$Venv = Join-Path $LocalRoot "venv"
$VenvPython = Join-Path $Venv "Scripts\python.exe"
$When = Get-Date -Format "yyyyMMdd_HHmmss"
$Results = Join-Path $LocalRoot ("results\" + $When)
New-Item -ItemType Directory -Path $Results -Force | Out-Null

if (Test-Path -LiteralPath $Reference) {
    $head = (& git -C $Reference rev-parse HEAD)
    Assert-Exit "Read pinned reference"
    if ($head.Trim() -ne $ReferenceSha) {
        throw "Reference differs from audited SHA; delete/repair the private reference yourself."
    }
} else {
    if ($Offline) { throw "Reference not cached. Run once without -Offline to prepare." }
    & git -C $Repo fetch origin $ReferenceSha
    Assert-Exit "Fetch exact read-only reference"
    & git -C $Repo -c core.autocrlf=false worktree add --detach $Reference $ReferenceSha
    Assert-Exit "Create byte-preserving read-only reference"
}
if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
    if ($Offline) { throw "Private venv not cached. Run setup once without -Offline." }
    Invoke-Py311 -m venv $Venv
}
$Pins = @(
    "pytest==8.3.5", "onnxruntime==1.20.1", "rapidocr-onnxruntime==1.4.4",
    "numpy==1.26.4", "Pillow==11.1.0", "rapidfuzz==3.12.2",
    "pytesseract==0.3.13", "psutil==6.1.1",
    "opencv-python-headless==4.10.0.84", "mss==10.0.0"
)
if (-not $Offline) {
    & $VenvPython -m pip install --disable-pip-version-check @Pins
    Assert-Exit "Install isolated pinned dependencies"
}
# Fail closed when an existing/offline venv drifts from exact package pins.
$CheckPackages = 'import importlib.metadata as m; import sys; pins=dict(x.split("==") for x in sys.argv[1:]); mismatches=[f"{k}={m.version(k)} (expected {v})" for k,v in pins.items() if m.version(k)!=v]; print("PINNED_DEPS_OK" if not mismatches else "PIN_MISMATCH "+", ".join(mismatches)); sys.exit(bool(mismatches))'
& $VenvPython -c $CheckPackages @Pins
Assert-Exit "Verify pinned dependency versions"

if (-not $TesseractExe) {
    if ($env:TESSERACT_PATH -and (Test-Path $env:TESSERACT_PATH)) {
        $TesseractExe = $env:TESSERACT_PATH
    } elseif (Get-Command tesseract -ErrorAction SilentlyContinue) {
        $TesseractExe = (Get-Command tesseract).Source
    } else {
        $candidate = Join-Path $env:ProgramFiles "Tesseract-OCR\tesseract.exe"
        if (Test-Path $candidate) { $TesseractExe = $candidate }
    }
}
if (-not $TesseractExe -or -not (Test-Path -LiteralPath $TesseractExe -PathType Leaf)) {
    throw "Tesseract English not found. Install Tesseract OCR (eng) and pass -TesseractExe explicitly if required. No system installation is performed automatically."
}
$env:TESSERACT_PATH = $TesseractExe
$langs = @(& $TesseractExe --list-langs 2>$null)
Assert-Exit "Tesseract language listing"
if (-not ($langs | Where-Object { $_.Trim() -eq "eng" })) {
    throw "Tesseract English language data (eng.traineddata) missing."
}
Write-Host "Tesseract English detected; exact pinned Python package versions verified."

$V4 = Join-Path $Models "ppocrv4.onnx"
$V5 = Join-Path $Models "ppocrv5_en.onnx"
$v4ok = Confirm-Model $V4 $V4Sha
$v5ok = Confirm-Model $V5 $V5Sha
if (-not $v4ok -or -not $v5ok -or
    -not (Test-Path -LiteralPath (Join-Path $Models "ppocr_keys_v1.txt"))) {
    if ($Offline) { throw "Pinned models/charset not cached. Run setup once without -Offline." }
    & $VenvPython (Join-Path $Repo "benchmarks\ocr_v11\fetch_models.py") $Models
    Assert-Exit "Fetch pinned model files"
}
if (-not (Confirm-Model $V4 $V4Sha) -or -not (Confirm-Model $V5 $V5Sha)) {
    throw "Pinned model verification failed."
}
Write-Host "Pinned models verified (full SHA-256). All subsequent OCR steps use cached local assets."

Push-Location $Repo
try {
    & $VenvPython -m pytest -q benchmarks/ocr_v11b/test_validation.py benchmarks/ocr_v11b/test_controlled.py benchmarks/ocr_v11c/test_v11c.py
    Assert-Exit "Safety and labeling tests"
    & $VenvPython -m benchmarks.ocr_v11b.stress_matcher --reference $Reference --out (Join-Path $Results "synthetic_stress.json")
    Assert-Exit "Synthetic text stress"
    if (-not $SkipControlled) {
        & $VenvPython -m benchmarks.ocr_v11b.run_inference --reference $Reference --models $Models --out $Results
        Assert-Exit "Real model frozen-original controlled inference"
    }
    & $VenvPython -m benchmarks.ocr_v11b.profile_windows --reference $Reference --models $Models --out (Join-Path $Results "windows_profile.json")
    Assert-Exit "Isolated cold-start, per-crop, triple-crop, CPU/RSS profiling"

    $ReportArgs = @("-m", "benchmarks.ocr_v11c.render_report",
                    "--profile", (Join-Path $Results "windows_profile.json"),
                    "--origin", "LOCAL_USER_EXECUTION_UNATTESTED",
                    "--out", (Join-Path $Results "REPORT.md"))
    if (-not $SkipControlled) {
        $ReportArgs += @("--controlled", (Join-Path $Results "v11b_results.json"))
    }
    & $VenvPython @ReportArgs
    Assert-Exit "Render readable local report"
} finally {
    Pop-Location
}
Write-Host ""
Write-Host "PASS — isolated Windows OCR benchmark completed outside League."
Write-Host "LOCAL-ONLY REPORT: $(Join-Path $Results 'REPORT.md')"
Write-Host "No images or local reports were uploaded. Actual game/OP.GG/holdout remain BLOCKED."
