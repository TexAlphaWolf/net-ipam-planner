# Security

## Model

ipam is a command line program that **reads JSON and CSV files and writes a few files**. It starts no service, opens no network
connection and runs no code from its input.

- **What it reads:** the plan JSON (strictly parsed: unknown keys, wrong types and malformed addresses are refused), the truth JSON
  given to `check --truth` and `report --truth`, the requests CSV given to `alloc --needs`, and a `report.json` or `bench.json`
  given to `render`.
- **What it writes:** only where the options say: `generate DIR` (it refuses to overwrite its files), `alloc -o`, `report --out`,
  `bench --out` and `render -o` and `--figure`.
- **Names are untrusted text.** They are printed as text and never interpreted; a name cannot contain `|`, which separates the two
  names of an overlap.
- **The Docker image** runs as an unprivileged user and works with a read-only root filesystem (plus `--tmpfs /tmp` for matplotlib's
  cache), no capabilities and no network (`--network none`); see `tools/docker_e2e.sh`.
- **No real data** is in the repository: the plans are synthetic. A plan of your own describes your network; keep it private and
  run the tool locally, as the image is built to be run.

## Reporting

If you find a vulnerability, please open a private security advisory on the GitHub repository (Security tab) rather than a public
issue.
