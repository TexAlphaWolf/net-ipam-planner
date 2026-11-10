# Changelog

## 1.0.0

First release.

- A strict reader of address plans in JSON (a supernet and subnets with optional VLAN, gateway and planned hosts), with its own
  IPv4 parser.
- 8 checks: outside the supernet, overlap, duplicate name, duplicate VLAN, gateway outside its subnet, gateway on the network or
  broadcast address, more hosts than the subnet holds, and host bits set.
- VLSM allocation (first fit, largest first) into a supernet, around existing subnets, and the free space as the shortest list of
  CIDR blocks.
- A literal implementation of the checks, the free space and the allocation on integers, and `ipam verify`, which compares it with
  the `ipaddress` implementation on generated plans, random messy plans and random allocations.
- A generator of consistent plans with injected faults and the list of what was injected, and a scoring of the findings against it.
- A report (JSON, Markdown, figure) rebuilt exactly from its JSON, and a benchmark of speed, detection and agreement.
- A command line with exit codes for a pipeline (0 ok, 1 findings or subnets that do not fit or a mismatch, 2 an error).
- Docker image (no network, read-only, no capabilities); CI on Python 3.11 to 3.14, Linux, Windows and macOS.
