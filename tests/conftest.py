from __future__ import annotations

import os
from typing import Any

from ipamplan.plan import Plan, Subnet

SEED = int(os.environ.get("IPAM_TEST_SEED", "1"))
DRAWS = int(os.environ.get("IPAM_TEST_DRAWS", "20"))


def plan(*subnets: Subnet | tuple[Any, ...], supernet: str = "10.0.0.0/24") -> Plan:
    return Plan("t", supernet, tuple(s if isinstance(s, Subnet) else Subnet(*s) for s in subnets))
