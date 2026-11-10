# Report: generated-120-1

Source: demo plan (synthetic, 120 subnets, seed 1, with injected faults). Supernet 10.0.0.0/19 (8,192 addresses), 122 subnets.

## 1. The address space

| | |
|---|---|
| Allocated | 4,004 addresses (48.9%) |
| Free | 4,188 addresses in 5 blocks |
| Largest free block | 10.0.16.0/20 (4,096 addresses) |
| Fragmentation | 2.2% of the free space is outside the largest free block |
| Hosts planned | 1,845 of 3,766 usable addresses of the subnets that state them (49.0%) |

## 2. Subnets by prefix

| Prefix | Subnets | Addresses each |
|---|---|---|
| /24 | 6 | 256 |
| /25 | 5 | 128 |
| /26 | 14 | 64 |
| /27 | 19 | 32 |
| /28 | 29 | 16 |
| /29 | 20 | 8 |
| /30 | 29 | 4 |

## 3. Findings

11 findings.

| Rule | Count | Meaning |
|---|---|---|
| outside_supernet | 1 | the subnet is not inside the supernet |
| overlap | 2 | two subnets share addresses |
| duplicate_name | 1 | two subnets have the same name |
| duplicate_vlan | 1 | two subnets have the same VLAN |
| gateway_outside | 2 | the gateway is not an address of its subnet |
| gateway_reserved | 1 | the gateway is the network or the broadcast address |
| over_capacity | 2 | more hosts are planned than the subnet can hold |
| host_bits | 1 | the address has bits set after the prefix (10.0.0.5/24) |

The first 11:

- `outside_supernet` net-00045: 172.16.0.0/24 is not inside 10.0.0.0/19
- `overlap` net-00002|overlap-000: net-00002 (10.0.2.0/24) and overlap-000 (10.0.2.0/25) share addresses
- `overlap` net-00016|overlap-001: net-00016 (10.0.8.192/26) and overlap-001 (10.0.8.192/27) share addresses
- `duplicate_name` net-00050: 2 subnets are called net-00050
- `duplicate_vlan` 3999: VLAN 3999 is used by net-00049, net-00001
- `gateway_outside` net-00059: gateway 203.0.113.1 of 10.0.13.224/28: the gateway is not an address of its subnet
- `gateway_outside` net-00040: gateway 203.0.113.1 of 10.0.12.160/27: the gateway is not an address of its subnet
- `gateway_reserved` net-00115: gateway 10.0.15.160 of 10.0.15.160/30: the gateway is the network or the broadcast address
- `over_capacity` net-00031: 31 hosts planned in 10.0.11.128/27, which holds 30
- `over_capacity` net-00041: 15 hosts planned in 10.0.12.192/28, which holds 14
- `host_bits` net-00102: 10.0.15.109/30 is not the network address of 10.0.15.108/30

## 4. Most unused room

| Subnet | Network | Usable addresses not planned |
|---|---|---|
| net-00004 | 10.0.4.0/24 | 201 |
| net-00003 | 10.0.3.0/24 | 188 |
| net-00000 | 10.0.0.0/24 | 155 |
| net-00005 | 10.0.5.0/25 | 100 |
| net-00008 | 10.0.6.128/25 | 91 |

## 5. Against the injected faults

11 of 11 injected faults found; 0 reports that are not an injected fault.

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
