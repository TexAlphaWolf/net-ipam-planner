# The full measurement on your own computer, in Docker (no network, read-only root, no capabilities), from Windows
# PowerShell: how fast a plan is checked and subnets are allocated, how many injected faults are found, and that the two
# implementations agree. It takes a few minutes: the literal implementation is slow on purpose.
# Usage: .\tools\run_full.ps1 [-Sizes 1000,10000,100000] [-RefMax 10000] [-AllocSizes 100,400,2000,10000] [-AllocRefMax 200]
#                            [-Repeat 5] [-Draws 50] [-Seeds 50] [-Out results]
param(
    [string]$Sizes = "1000,10000,100000",
    [int]$RefMax = 10000,
    [string]$AllocSizes = "100,400,2000,10000",
    [int]$AllocRefMax = 200,
    [int]$Repeat = 5,
    [int]$Draws = 50,
    [int]$Seeds = 50,
    [string]$Out = "results"
)
# Windows PowerShell 5.1 turns anything a program writes on stderr into an error under "Stop": docker and ipam print
# their progress there, so only the exit code is looked at.
$ErrorActionPreference = "Continue"
New-Item -ItemType Directory -Force -Path $Out | Out-Null
$outFull = (Resolve-Path -LiteralPath $Out).Path

docker build -t ipam .
if ($LASTEXITCODE -ne 0) { Write-Host "docker build failed"; exit 1 }

Write-Host "== bench (sizes $Sizes, $Repeat runs each, $Draws random cases compared, $Seeds plans for detection) =="
docker run --rm --read-only --tmpfs /tmp --cap-drop ALL --security-opt no-new-privileges --network none -v "${outFull}:/out" ipam bench --sizes $Sizes --ref-max $RefMax --alloc-sizes $AllocSizes --alloc-ref-max $AllocRefMax --repeat $Repeat --draws $Draws --seeds $Seeds --out /out
if ($LASTEXITCODE -ne 0) { Write-Host "bench failed (exit code $LASTEXITCODE)"; exit 1 }
Write-Host "Done. Send me $Out\bench.json, $Out\bench.md and $Out\summary.png."
