# Scenario 3: Network Connectivity and Routing Issues

## Support Ticket

**Ticket ID**: SUP-2024-3291
**Priority**: P1 - Critical
**Category**: Network / Connectivity
**Status**: Escalated to Engineering

---

## Customer Report

**From**: Platform Admin, MegaCorp Industries
**Subject**: VPN connectivity drops, subnet allocation failures, and security group rules not working

---

### Issue Description

We've been experiencing multiple network-related issues since last week that are severely impacting our ability to provision infrastructure:

#### 1. Overlapping CIDR Allocations

When we provision new subnets, the system sometimes allocates CIDR blocks that overlap with existing subnets. This morning we requested a /24 in our production VPC and got 10.0.1.0/24, which overlaps with our existing 10.0.1.0/25 and 10.0.1.128/25 subnets.

```
Existing subnets:
  - 10.0.1.0/25   (production-web)
  - 10.0.1.128/25 (production-api)

New allocation request: /24
Allocated: 10.0.1.0/24  <-- OVERLAPS WITH BOTH!
```

#### 2. VPN Tunnel Packet Loss

Our site-to-site VPN tunnels are experiencing intermittent packet loss for packets larger than 1440 bytes. Smaller packets work fine. We've verified our on-premise router is configured correctly with MTU 1500.

The platform shows our tunnel MTU as 1500, but packets > 1440 bytes are being silently dropped. It's like IPsec overhead isn't being accounted for.

#### 3. Firewall Rules Evaluated in Wrong Order

We have the following security group rules:

```
Priority 100: DENY tcp/22 from 0.0.0.0/0
Priority 200: ALLOW tcp/22 from 10.0.0.0/8
```

We expected SSH to be denied from the internet (priority 100) but allowed from internal IPs (priority 200). Instead, ALL SSH traffic is being allowed. It seems like the lower priority number (100) is being evaluated LAST instead of FIRST.

#### 4. DNS Resolution Hangs

Some of our internal DNS lookups are hanging indefinitely. We traced it to a circular CNAME chain:

```
service-a.internal -> service-b.internal -> service-a.internal
```

The resolver should detect this and fail fast, but instead it appears to loop forever.

#### 5. Subnet Exhaustion Not Detected

Our monitoring shows a subnet with 256 allocated IPs out of 256 total (/24). But when we try to launch a new instance, it attempts allocation and fails instead of telling us the subnet is exhausted upfront. The exhaustion check seems to think we still have capacity when allocated == total.

#### 6. Security Group Deduplication Removing Legitimate Rules

We have two rules with the same port but different sources:

```
Rule A: ALLOW tcp/443 from 10.0.0.0/8
Rule B: ALLOW tcp/443 from 192.168.0.0/16
```

After applying, only Rule A exists. Rule B was removed as a "duplicate" even though they have different source CIDR blocks.

#### 7. NAT Gateway Port Exhaustion Under Load

During our load tests, we're seeing NAT gateway port allocation failures. Our monitoring shows race conditions where two connections are assigned the same ephemeral port, causing one to fail.

#### 8. VPC Peering One-Way Traffic

We established peering between VPC-A and VPC-B. Traffic flows from A to B, but not from B to A. The peering configuration shows:
- Route A->B: Active
- Route B->A: Active

But the `check_peering_routing` function returns `True` even when only one direction works.

---

## Engineering Notes

### Route Propagation Delays

Noticed that route table updates are taking 30+ seconds to propagate across availability zones. Some instances are using stale routes during this window. There's no propagation delay handling in the routing code.

### Load Balancer Health Check Flapping

Health checks are flapping between healthy and unhealthy states. Investigation shows the thresholds are too sensitive:

```
Current config:
  unhealthy_threshold: 1  (1 failure = mark unhealthy)
  healthy_threshold: 1    (1 success = mark healthy)

Expected:
  unhealthy_threshold: 3
  healthy_threshold: 2
```

---

## Affected Components

- `services/network/views.py` - CIDR allocation, firewall rules, DNS, subnets
- `services/loadbalancer/main.py` - Health check thresholds
- `shared/utils/distributed.py` - NAT port allocation concurrency

---

## Test Failures Related

```
FAILED tests/integration/test_network.py::TestNetwork::test_cidr_no_overlap
FAILED tests/integration/test_network.py::TestNetwork::test_firewall_rule_priority_order
FAILED tests/integration/test_network.py::TestNetwork::test_vpn_mtu_calculation
FAILED tests/integration/test_network.py::TestNetwork::test_dns_circular_cname_detection
FAILED tests/integration/test_network.py::TestNetwork::test_subnet_exhaustion_at_limit
FAILED tests/integration/test_network.py::TestNetwork::test_security_group_dedup_includes_source
FAILED tests/integration/test_network.py::TestNetwork::test_nat_port_atomic_allocation
FAILED tests/integration/test_network.py::TestNetwork::test_peering_requires_bidirectional
FAILED tests/chaos/test_health_check_stability.py::test_health_check_flapping
```

---

## Business Impact

- **Revenue**: $45,000/hour lost due to production traffic being blocked
- **Compliance**: Security audit finding for firewall rule misconfiguration
- **Operations**: Network team spending 60% of time on manual interventions
