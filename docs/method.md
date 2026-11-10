# Method

## The plan file

A plan is a JSON object with a `supernet` (CIDR, no host bits), a list of `subnets` and an optional `name`. A subnet has a `name`
(1 to 80 characters, no `|`) and a `cidr`, and optionally a `vlan` (1 to 4094), a `gateway` (an IPv4 address) and `hosts` (the
number of hosts planned, at least 0). The reader refuses unknown keys, wrong types and malformed addresses, with the place
(`subnets[3].cidr`). A `cidr` may have host bits set (`10.0.0.5/24`); that is a finding, not an error, and the network it names
is `10.0.0.0/24`.

Addresses are parsed with a small parser of the project (four decimal octets without leading zeros, a prefix from 0 to 32) and not
with `ipaddress`, so the loader does not depend on the library under the fast implementation.

## Definitions

- A subnet's **block** is the addresses from `address & mask` to `address | ~mask` (the network and the broadcast address are the
  first and the last).
- **Usable hosts**: all but those two addresses, so `2^(32-p) - 2` for a prefix `p` up to 30; a /31 holds 2 (point to point) and a
  /32 holds 1.
- The **supernet** is the space the plan lives in; subnets are expected inside it.

## The rules

Findings are ordered by rule in the order of this table and, within a rule, by the position of the subnet in the file (for an
overlap, by the positions of the two). A finding is a rule and a subject.

| Rule | Subject | A finding when |
|---|---|---|
| `outside_supernet` | the subnet | its block is not entirely inside the supernet (a block larger than the supernet is outside) |
| `overlap` | `a\|b`, by position, `a` first | two blocks share an address: one contains the other, or they are equal; adjacent blocks do not overlap; subnets outside the supernet are included |
| `duplicate_name` | the name | more than one subnet has it; reported once, at the first |
| `duplicate_vlan` | the VLAN number | more than one subnet has it; reported once, at the first |
| `gateway_outside` | the subnet | a gateway is given and is not an address of the block |
| `gateway_reserved` | the subnet | the gateway is in the block and is the network or the broadcast address, for a prefix up to /30 (on a /31 and a /32 every address is a host) |
| `over_capacity` | the subnet | `hosts` is given and is more than the usable hosts |
| `host_bits` | the subnet | the address written has bits set after the prefix |

## Free space

The supernet minus the union of the blocks (a block is clipped to the supernet), as the **shortest list of CIDR blocks**: each gap
between used intervals is covered by the largest aligned blocks that fit. `used` counts each address once, however many subnets
cover it. The fast implementation merges the sorted intervals and uses `summarize_address_range`; the literal one walks the
sorted blocks with a cursor and repeatedly takes the largest aligned power of two that fits.

## Allocation

A request is a name and a number of hosts. Its prefix is the longest one, at most /30, whose subnet holds that many hosts (hosts 1
and 2 get a /30; 255 hosts get a /23). Requests are placed **largest first** (shortest prefix first; ties by name, then by order),
each at the **lowest aligned block that is free**, where free means not covered by an existing subnet (clipped to the supernet)
or by a block placed earlier. A request that finds no block is reported as unplaced and the others still go in.

Because block sizes are powers of two and are placed largest first, an empty supernet loses nothing to alignment: all requests
are placed exactly when their block sizes add up to no more than the supernet (a test checks this). With existing subnets in the
way, first fit is not guaranteed to find a placement when one exists, and it does not try to leave room for growth.

## Two implementations

`check.py` uses `ipaddress`: the overlaps by a sweep over the blocks sorted by start (larger first) with a stack of the blocks that
contain the current one, since two CIDR blocks overlap only if one contains the other; the free space by merged intervals; the
allocation over a sorted list of free intervals. `reference.py` works on integers: every pair of subnets is compared, the free
space is built with a cursor, and the allocation tries each aligned candidate against every used block. `ipam verify` compares
findings, free blocks, used and free addresses, and placements, and the allocations are also checked for soundness on their own.

## The generator

`generate(subnets, seed, faults)` draws prefixes (mostly /30 to /26), sorts them largest first, carves them one after another
from the start of the smallest `10.0.0.0/p` with room for twice the addresses, gives each a VLAN (while there are VLAN numbers
below 3995; the numbers above are kept for faults), its first host as gateway and a number of hosts that fits, and shuffles the
order. It then injects faults into subnets that no other fault touches, one rule at a time, and keeps the list: a subnet moved
to `172.16.x.0/24`, a smaller subnet put inside another, a name or a VLAN copied, a gateway set to `203.0.113.1` or to the network
address, hosts set to one above the capacity, host bits set in the address.
