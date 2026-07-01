param()

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

$dumpDir = Join-Path $scriptDir "mir_dump_dummy"
if (Test-Path $dumpDir) {
    Get-ChildItem $dumpDir -Filter *.mir -File | Remove-Item
} else {
    New-Item -ItemType Directory -Path $dumpDir | Out-Null
}

$env:RUSTFLAGS = "-Z dump-mir=main -Z mir-opt-level=3 -Z dump-mir-dir=mir_dump_dummy"
cargo +nightly build --release

