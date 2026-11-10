#!/usr/bin/env bash
# End to end inside the image (read-only root, no capabilities, no network): a plan is generated, checked, scored against its
# truth, extended with new subnets, reported (the report is rebuilt exactly from its JSON), the two implementations are
# compared and the benchmark runs small. Needs Docker. Usage: tools/docker_e2e.sh [image]
set -euo pipefail
IMAGE="${1:-ipam}"
VOL="ipam-e2e-$$"
TMP="$(mktemp -d)"
trap 'docker volume rm -f "$VOL" >/dev/null 2>&1 || true; rm -rf "$TMP"' EXIT

[ "$(docker run --rm --entrypoint id "$IMAGE" -u)" != 0 ]   # not root
docker volume create "$VOL" >/dev/null
docker run --rm --user 0 -v "$VOL":/data --entrypoint chown "$IMAGE" 10001 /data

RUN=(docker run --rm --read-only --tmpfs /tmp --cap-drop ALL --security-opt no-new-privileges --network none -v "$VOL":/data "$IMAGE")
cat_file() { docker run --rm --entrypoint cat -v "$VOL":/data "$IMAGE" "$1" > "$2"; }

"${RUN[@]}" generate /data/dc --subnets 60 --seed 3 | grep -q '62 subnets, 11 injected faults'
set +e; out="$("${RUN[@]}" check /data/dc/plan.json --truth /data/dc/truth.json)"; rc=$?; set -e
[ "$rc" = 1 ]                                                     # there are findings
grep -q '11 findings in 62 subnets' <<<"$out"
grep -q 'against the injected faults: 11 of 11 found, 0 extra' <<<"$out"

"${RUN[@]}" generate /data/clean --subnets 40 --clean >/dev/null
out="$("${RUN[@]}" check /data/clean/plan.json)"                  # exit code 0: no findings
grep -q '^0 findings in 40 subnets' <<<"$out"

out="$("${RUN[@]}" alloc --plan /data/clean/plan.json --need web=100 --need lab=6 -o /data/clean/more.json)"
grep -q '^web ' <<<"$out"
out="$("${RUN[@]}" check /data/clean/more.json)"
grep -q '^0 findings in 42 subnets' <<<"$out"
"${RUN[@]}" free /data/clean/more.json | grep -q 'free addresses in'

out="$("${RUN[@]}" report --out /data/out)"
grep -q '11 findings:' <<<"$out"
grep -q 'against the injected faults: 11 of 11 found' <<<"$out"
cat_file /data/out/report.json "$TMP/report.json"
grep -q '"kind": "report"' "$TMP/report.json"
cat_file /data/out/report.md "$TMP/report.md"
"${RUN[@]}" render /data/out/report.json -o /data/out/again.md >/dev/null
cat_file /data/out/again.md "$TMP/again.md"
cmp "$TMP/again.md" "$TMP/report.md"                              # the report is rebuilt exactly from the JSON
cat_file /data/out/summary.png "$TMP/summary.png"
[ "$(head -c 4 "$TMP/summary.png" | tail -c 3)" = "PNG" ]

out="$("${RUN[@]}" verify --draws 5)"
grep -q '^12 of 12 comparisons agree with the literal implementation' <<<"$out"

"${RUN[@]}" bench --sizes 100,200 --ref-max 200 --alloc-sizes 20,40 --alloc-ref-max 40 --repeat 1 --draws 2 --seeds 3 --out /data/bench >/dev/null
cat_file /data/bench/bench.json "$TMP/bench.json"
grep -q '"ok": true' "$TMP/bench.json"

set +e; "${RUN[@]}" check /data/nope.json >/dev/null 2>&1; rc=$?; set -e   # a missing file is exit code 2
[ "$rc" = 2 ]
echo "docker end-to-end: OK"
