# Benchmark

Run on Linux x86_64, 12 CPUs, Python 3.14.10; seed 1; each time is the median of 5 runs (at most 3 for the literal implementation); command `bench --sizes 1000,10000,100000 --ref-max 10000 --alloc-sizes 100,400,2000,10000 --alloc-ref-max 200 --repeat 5 --draws 50 --seeds 50 --out /out`.

## 1. Checking a plan: the standard library against the literal implementation

| Subnets | Standard library | Literal | Ratio | Findings |
|---|---|---|---|---|
| 1,000 | 16.2 ms | 71.5 ms | 4.4x | 0 |
| 10,000 | 202.4 ms | 6.40 s | 31.6x | 0 |
| 100,000 | 2.33 s | - | - | 0 |

## 2. Allocating subnets

| Requests | Standard library | Literal | Ratio | Placed |
|---|---|---|---|---|
| 100 | 237 us | 77.3 ms | 326.0x | 100 |
| 400 | 1.1 ms | - | - | 400 |
| 2,000 | 5.6 ms | - | - | 2,000 |
| 10,000 | 31.4 ms | - | - | 10,000 |

## 3. Detection of injected faults

50 generated plans of 200 subnets, each given 0 to 2 faults of each of the 8 kinds: 375 injected, 375 found, 0 missed, 0 reports that are not an injected fault; 50 plans without faults gave 0 findings.

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

## 4. Agreement

102 comparisons (2 generated plans, 50 random plans and 50 random allocations): 8,296 values compared. All agree.
