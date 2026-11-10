# Limitations

- **The detection score is a ceiling.** The faults are injected by the same code base that defines the rules. 375 of 375 found
  says the two agree, not that the checks cover what goes wrong in a real plan. A well-formed but wrong subnet (the wrong site,
  the wrong size, a gateway that is a valid address of the wrong device) is not a finding of any rule here.
- **The plans are synthetic.** The demo and the benchmark use generated plans: mostly small subnets carved in order from one
  10.0.0.0 supernet, each with its first host as gateway. Real plans are irregular and grow in layers.
- **One routing domain.** Two subnets with the same addresses are an `overlap`, and two with the same VLAN a `duplicate_vlan`.
  Where VRFs, sites or customers legitimately reuse addresses or VLAN numbers, those findings are noise; the tool has no notion of
  VRF, site or VLAN scope.
- **IPv4 only.** The reader refuses an IPv6 address. The sweep and the arithmetic would carry over to 128 bits; the file format,
  the generator and the host-count rules (/64 networks, no broadcast) would not.
- **First fit is not optimal.** Into an empty supernet nothing is lost, but with existing subnets in the way a request can fail
  although a different placement would have fitted, and nothing is left aside for growth. Prefixes are at most /30 and at least
  what the host count needs; there is no headroom option.
- **A plan is a list, not a hierarchy.** Subnets are not nested into regions or sites, there is no summarisation advice, and the
  free space is the supernet minus everything, not per parent block.
- **No state and no discovery.** There is no database, no history of changes, no DHCP, no lease or device data and no import from
  a live network; a plan is a JSON file you keep.
- **The checks read the plan, not the network.** Whether a gateway answers, or a subnet is configured as planned, is out of scope.
