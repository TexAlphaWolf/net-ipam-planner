# Analysis

Source: [`report.json`](report.json) (the demo plan: 120 subnets generated with seed 1, plus 2 added by the overlap faults, in
10.0.0.0/19, with injected faults) and [`bench.json`](bench.json) (one run in Docker on Linux x86_64 with 12 CPUs, Python 3.14.10;
medians of 5 runs, 3 for the literal implementation; 50 generated plans of 200 subnets for the detection). **The plans are
synthetic**: they come from a generator built to be plausible, and the faults are the ones that generator injects. Read the
structure of the results, not the addresses.

## 1. The demo plan

122 subnets in 10.0.0.0/19 (8,192 addresses): 6 /24, 5 /25, 14 /26, 19 /27, 29 /28, 20 /29 and 29 /30. They take 4,004 addresses
(48.9%) and leave 4,188 in 5 CIDR blocks, the largest 10.0.16.0/20 (4,096 addresses): only 2.2% of the free space lies outside it,
because the generator carves the subnets from the bottom of the supernet, largest first, and the injected faults move a few out
of the way. Where the planned hosts are stated they are 1,845 of 3,766 usable addresses (49.0%).

The checks report 11 findings, and the generator says it injected 11 faults:

| Rule | Injected | Found | Missed | Extra |
|---|---|---|---|---|
| outside_supernet | 1 | 1 | 0 | 0 |
| overlap | 2 | 2 | 0 | 0 |
| duplicate_name | 1 | 1 | 0 | 0 |
| duplicate_vlan | 1 | 1 | 0 | 0 |
| gateway_outside | 2 | 2 | 0 | 0 |
| gateway_reserved | 1 | 1 | 0 | 0 |
| over_capacity | 2 | 2 | 0 | 0 |
| host_bits | 1 | 1 | 0 | 0 |

- **An overlap is a pair.** net-00002 (10.0.2.0/24) and overlap-000 (10.0.2.0/25) are one finding, not two, and a /25 inside a /24
  is found whichever comes first in the file.
- **Capacity is about usable addresses.** net-00031 has 31 hosts planned in a /27, which holds 30; net-00041 has 15 in a /28, which
  holds 14. The 2 addresses lost to the network and the broadcast address are the usual way a plan that adds up on paper does not.
- **Gateways have two ways to be wrong.** Two are not in their subnet at all (203.0.113.1), and one, net-00115, is the network
  address of its /30 (10.0.15.160), which is a valid address to type and an invalid one to use.

## 2. Detection over 50 plans

Seeds 1 to 50, 200 subnets each; every plan is built consistent (0 findings in all 50) and then given 0 to 2 faults of each of the
8 kinds.

| Rule | Injected | Found | Missed | Extra |
|---|---|---|---|---|
| outside_supernet | 45 | 45 | 0 | 0 |
| overlap | 53 | 53 | 0 | 0 |
| duplicate_name | 49 | 49 | 0 | 0 |
| duplicate_vlan | 50 | 50 | 0 | 0 |
| gateway_outside | 43 | 43 | 0 | 0 |
| gateway_reserved | 45 | 45 | 0 | 0 |
| over_capacity | 44 | 44 | 0 | 0 |
| host_bits | 46 | 46 | 0 | 0 |

375 injected, 375 found, 0 missed, 0 extra. This says the generator and the rules mean the same thing. It is a ceiling: the
injected faults are the ones the rules were written for, and a real plan has mistakes of other kinds (a subnet in the wrong
site, a size that is legal and wrong) that no rule here describes.

## 3. Speed of the check

| Subnets | Standard library | Literal | Ratio | Findings |
|---|---|---|---|---|
| 1,000 | 16.2 ms | 71.5 ms | 4.4x | 0 |
| 10,000 | 202.4 ms | 6.40 s | 31.6x | 0 |
| 100,000 | 2.33 s | - | - | 0 |

The time per subnet of the `ipaddress` implementation goes from 16.2 us at 1,000 subnets to 20.2 us at 10,000 and 23.3 us at
100,000: a little worse than linear, because the overlap sweep sorts the blocks. The literal implementation compares every pair, so
10 times the subnets cost 90 times the time (71.5 ms to 6.40 s), and it was not run at 100,000. These are the plans of the
generator without faults; a plan with many overlaps would make the sweep report more pairs, but it reports only the pairs that
overlap, so the cost follows the findings and not the square of the size.

## 4. Speed of the allocation

| Requests | Standard library | Literal | Ratio | Placed |
|---|---|---|---|---|
| 100 | 237 us | 77.3 ms | 326.0x | 100 |
| 400 | 1.1 ms | - | - | 400 |
| 2,000 | 5.6 ms | - | - | 2,000 |
| 10,000 | 31.4 ms | - | - | 10,000 |

The requests are random sizes (2 to 254 hosts) into an empty 10.0.0.0/8. The `ipaddress` implementation costs 2.4 us a request at
100, 2.7 us at 400, 2.8 us at 2,000 and 3.1 us at 10,000, almost linear; the literal one tries every aligned candidate against
every used block and was timed only up to 200 requests. In an empty supernet every request is placed, as the block sizes add up
to far less than the 16.7 million addresses.

## 5. Agreement

102 comparisons (2 generated plans, 50 random messy plans and 50 random allocations): 8,296 values compared (findings, free blocks,
address counts and placements), all equal. The random plans have overlaps, subnets outside the supernet, host bits, repeated names
and VLANs and odd gateways, and in the tests every rule appears in them; the random allocations have existing subnets, requests
larger than the supernet and several supernet sizes. Allocations are also checked for being aligned, inside the supernet, big
enough and disjoint without using either implementation's search.
