# End to end inside the image, from Windows PowerShell: a plan is generated, checked, scored against its truth, extended with
# new subnets, reported (the report is rebuilt exactly from its JSON), the two implementations are compared and the benchmark
# runs small (read-only root, no capabilities, no network). Needs Docker Desktop.
# Usage: .\tools\docker_e2e.ps1 [-Image ipam]
param([string]$Image = "ipam")
$ErrorActionPreference = "Stop"

$id = Get-Random
$vol = "ipam-e2e-$id"
$secure = @("--read-only", "--tmpfs", "/tmp", "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--network", "none", "-v", "${vol}:/data")

# Windows PowerShell 5.1 turns a program's message on stderr into an error under "Stop": the commands that are expected to
# fail run with errors not terminating, and only their exit code is looked at.
function Invoke-IpamCode([int[]]$Allowed, [string[]]$IpamArgs) {
    $old = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $out = docker run --rm @secure $Image @IpamArgs 2>&1
    $code = $LASTEXITCODE
    $ErrorActionPreference = $old
    if ($Allowed -notcontains $code) { throw "ipam $IpamArgs exited with $code : $out" }
    ($out | Out-String)
}
function Invoke-Ipam([string[]]$IpamArgs) { Invoke-IpamCode @(0) $IpamArgs }
function Read-Volume($path) {
    $out = docker run --rm --entrypoint cat -v "${vol}:/data" $Image $path 2>$null
    if ($LASTEXITCODE -ne 0) { throw "cannot read $path" }
    ($out | Out-String)
}
function Assert-Contains($text, $needle) { if ($text -notmatch [regex]::Escape($needle)) { throw "expected '$needle' in: $text" } }

try {
    docker volume create $vol | Out-Null
    docker run --rm --user 0 -v "${vol}:/data" --entrypoint chown $Image 10001 /data
    if ($LASTEXITCODE -ne 0) { throw "could not prepare the volume" }

    Assert-Contains (Invoke-Ipam @("generate", "/data/dc", "--subnets", "60", "--seed", "3")) "62 subnets, 11 injected faults"
    $chk = Invoke-IpamCode @(1) @("check", "/data/dc/plan.json", "--truth", "/data/dc/truth.json")
    Assert-Contains $chk "11 findings in 62 subnets"
    Assert-Contains $chk "against the injected faults: 11 of 11 found, 0 extra"

    Invoke-Ipam @("generate", "/data/clean", "--subnets", "40", "--clean") | Out-Null
    Assert-Contains (Invoke-Ipam @("check", "/data/clean/plan.json")) "0 findings in 40 subnets"
    Assert-Contains (Invoke-Ipam @("alloc", "--plan", "/data/clean/plan.json", "--need", "web=100", "--need", "lab=6", "-o", "/data/clean/more.json")) "web"
    Assert-Contains (Invoke-Ipam @("check", "/data/clean/more.json")) "0 findings in 42 subnets"
    Assert-Contains (Invoke-Ipam @("free", "/data/clean/more.json")) "free addresses in"

    $rep = Invoke-Ipam @("report", "--out", "/data/out")
    Assert-Contains $rep "11 findings:"
    Assert-Contains $rep "against the injected faults: 11 of 11 found"
    $md = Read-Volume "/data/out/report.md"
    Invoke-Ipam @("render", "/data/out/report.json", "-o", "/data/out/again.md") | Out-Null
    if ((Read-Volume "/data/out/again.md") -ne $md) { throw "the report rebuilt from the JSON is not identical" }

    Assert-Contains (Invoke-Ipam @("verify", "--draws", "5")) "12 of 12 comparisons agree with the literal implementation"

    Invoke-Ipam @("bench", "--sizes", "100,200", "--ref-max", "200", "--alloc-sizes", "20,40", "--alloc-ref-max", "40", "--repeat", "1", "--draws", "2", "--seeds", "3", "--out", "/data/bench") | Out-Null
    Assert-Contains (Read-Volume "/data/bench/bench.json") '"ok": true'

    Invoke-IpamCode @(2) @("check", "/data/nope.json") | Out-Null
    Write-Host "docker end-to-end: OK"
}
finally {
    $ErrorActionPreference = "Continue"
    docker volume rm -f $vol 2>&1 | Out-Null
}
