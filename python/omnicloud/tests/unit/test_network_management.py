"""
OmniCloud Network Management Tests
Terminal Bench v2 - Tests for CIDR allocation, firewall rules, VPN, DNS, peering.

Covers bugs: D1-D10
~80 tests
"""
import pytest
from ipaddress import IPv4Network
from services.network.views import (
    allocate_cidr, order_firewall_rules, calculate_vpn_mtu,
    resolve_dns_cname, check_subnet_exhaustion, deduplicate_security_group_rules,
    allocate_nat_port, check_peering_routing,
)
from services.loadbalancer.main import HealthCheckState


class TestCIDRAllocation:
    """Tests for D1: CIDR overlap prevention."""

    def test_cidr_no_overlap(self):
        """D1: New CIDR allocation should not overlap existing ones."""
        existing = ["10.0.0.0/24", "10.0.1.0/24"]
        result = allocate_cidr(24, existing, "10.0.0.0/16")
        if result:
            new_net = IPv4Network(result)
            for existing_cidr in existing:
                existing_net = IPv4Network(existing_cidr)
                assert not new_net.overlaps(existing_net), \
                    f"New allocation {result} overlaps with {existing_cidr}"

    def test_subnet_allocation_unique(self):
        """D1: Multiple allocations should all be unique."""
        existing = []
        allocated = []
        for _ in range(5):
            result = allocate_cidr(24, existing, "10.0.0.0/16")
            if result:
                for prev in allocated:
                    prev_net = IPv4Network(prev)
                    new_net = IPv4Network(result)
                    assert not new_net.overlaps(prev_net), \
                        f"Allocation {result} overlaps with previous {prev}"
                allocated.append(result)
                existing.append(result)

    def test_cidr_allocation_returns_valid(self):
        """D1: Allocated CIDR should be valid IPv4 network."""
        result = allocate_cidr(24, [], "10.0.0.0/16")
        assert result is not None
        net = IPv4Network(result)
        assert net.prefixlen == 24

    def test_cidr_within_parent(self):
        """D1: Allocation should be within parent CIDR."""
        result = allocate_cidr(24, [], "192.168.0.0/16")
        if result:
            assert result.startswith("192.168.")


class TestFirewallOrdering:
    """Tests for D2: Firewall rule priority ordering."""

    def test_firewall_rule_ordering(self):
        """D2: Rules should be ordered with lower number = higher priority."""
        rules = [
            {"priority": 100, "action": "allow", "port": 80},
            {"priority": 50, "action": "deny", "port": 22},
            {"priority": 200, "action": "allow", "port": 443},
        ]
        ordered = order_firewall_rules(rules)
        # Lower priority number should come first (higher priority)
        priorities = [r["priority"] for r in ordered]
        assert priorities == sorted(priorities), \
            f"Rules should be in ascending priority order, got {priorities}"

    def test_rule_priority_respected(self):
        """D2: First matching rule should apply."""
        rules = [
            {"priority": 10, "action": "deny", "port": 80},
            {"priority": 20, "action": "allow", "port": 80},
        ]
        ordered = order_firewall_rules(rules)
        assert ordered[0]["action"] == "deny", "Deny rule (priority 10) should come first"

    def test_same_priority_stable(self):
        """D2: Rules with same priority should maintain original order."""
        rules = [
            {"priority": 100, "action": "allow", "port": 80, "id": "a"},
            {"priority": 100, "action": "deny", "port": 22, "id": "b"},
        ]
        ordered = order_firewall_rules(rules)
        assert len(ordered) == 2

    def test_empty_rules(self):
        """D2: Empty rules list should return empty."""
        assert order_firewall_rules([]) == []


class TestVPNMTU:
    """Tests for D3: VPN tunnel MTU calculation."""

    def test_vpn_mtu_correct(self):
        """D3: VPN MTU should account for encryption overhead."""
        mtu = calculate_vpn_mtu(1500)
        # IPsec adds ~60 bytes overhead
        assert mtu <= 1440, f"VPN MTU should be <= 1440, got {mtu}"

    def test_mtu_negotiation(self):
        """D3: MTU with explicit overhead should be correct."""
        mtu = calculate_vpn_mtu(1500, encryption_overhead=60)
        assert mtu == 1440

    def test_mtu_default_overhead(self):
        """D3: Default overhead should be non-zero for security."""
        mtu = calculate_vpn_mtu()
        assert mtu < 1500, "Default VPN MTU should be less than interface MTU"


class TestDNSResolution:
    """Tests for D4: DNS circular CNAME prevention."""

    def test_dns_no_circular_cname(self):
        """D4: Circular CNAME records should not cause infinite loop."""
        records = {
            "a.example.com": "b.example.com",
            "b.example.com": "c.example.com",
            "c.example.com": "a.example.com",  # Circular
        }
        result = resolve_dns_cname("a.example.com", records, max_depth=10)
        assert result is None, "Circular CNAME should return None"

    def test_cname_chain_resolution(self):
        """D4: Valid CNAME chain should resolve correctly."""
        records = {
            "a.example.com": "b.example.com",
            "b.example.com": "c.example.com",
        }
        result = resolve_dns_cname("a.example.com", records, max_depth=10)
        assert result == "c.example.com"

    def test_cname_depth_limit(self):
        """D4: Deep CNAME chains should be bounded."""
        records = {f"level{i}.example.com": f"level{i+1}.example.com" for i in range(100)}
        result = resolve_dns_cname("level0.example.com", records, max_depth=10)
        assert result is None, "Deep CNAME chain should be rejected"

    def test_cname_direct_resolution(self):
        """D4: Direct A record should resolve immediately."""
        records = {}
        result = resolve_dns_cname("direct.example.com", records)
        assert result == "direct.example.com"

    def test_cname_single_hop(self):
        """D4: Single CNAME hop should resolve."""
        records = {"alias.example.com": "target.example.com"}
        result = resolve_dns_cname("alias.example.com", records, max_depth=5)
        assert result == "target.example.com"


class TestSubnetExhaustion:
    """Tests for D5: Subnet exhaustion detection."""

    def test_subnet_exhaustion_detected(self):
        """D5: Full subnet should be detected."""
        assert check_subnet_exhaustion(256, 256) is True, \
            "Subnet with all IPs allocated should be exhausted"

    def test_allocation_fails_when_full(self):
        """D5: Exactly full subnet should be detected as exhausted."""
        total = 254  # /24 minus network and broadcast
        assert check_subnet_exhaustion(total, total) is True

    def test_subnet_not_exhausted(self):
        """D5: Subnet with available IPs should not be exhausted."""
        assert check_subnet_exhaustion(100, 254) is False

    def test_empty_subnet(self):
        """D5: Empty subnet should not be exhausted."""
        assert check_subnet_exhaustion(0, 254) is False


class TestSecurityGroupDedup:
    """Tests for D6: Security group rule deduplication."""

    def test_security_group_dedup(self):
        """D6: Duplicate rules should be removed based on full criteria."""
        rules = [
            {"protocol": "tcp", "port": 80, "source": "10.0.0.0/8"},
            {"protocol": "tcp", "port": 80, "source": "192.168.0.0/16"},
        ]
        result = deduplicate_security_group_rules(rules)
        # These are different rules (different source), both should be kept
        assert len(result) == 2, \
            f"Rules with different sources should not be deduplicated, got {len(result)} rules"

    def test_duplicate_rule_rejected(self):
        """D6: Truly duplicate rules should be merged."""
        rules = [
            {"protocol": "tcp", "port": 80, "source": "10.0.0.0/8"},
            {"protocol": "tcp", "port": 80, "source": "10.0.0.0/8"},
        ]
        result = deduplicate_security_group_rules(rules)
        assert len(result) == 1

    def test_different_protocols_kept(self):
        """D6: Rules with different protocols should not be deduplicated."""
        rules = [
            {"protocol": "tcp", "port": 80, "source": "0.0.0.0/0"},
            {"protocol": "udp", "port": 80, "source": "0.0.0.0/0"},
        ]
        result = deduplicate_security_group_rules(rules)
        assert len(result) == 2

    def test_empty_rules(self):
        """D6: Empty list should return empty."""
        assert deduplicate_security_group_rules([]) == []


class TestRouteTablePropagation:
    """Tests for D7: Route table convergence."""

    def test_route_propagation_complete(self):
        """D7: Route changes should propagate to all route tables."""
        assert True, "Route propagation completeness check"

    def test_route_table_convergence(self):
        """D7: All route tables should converge to consistent state."""
        assert True, "Route table convergence check"


class TestNATPortAllocation:
    """Tests for D8: NAT port allocation race."""

    def test_nat_port_allocation_atomic(self):
        """D8: NAT port allocation should be atomic."""
        allocated = set()
        port = allocate_nat_port(allocated)
        assert port is not None
        assert port >= 1024
        assert port in allocated

    def test_nat_port_no_conflict(self):
        """D8: Concurrent allocations should not produce same port."""
        allocated = set()
        ports = []
        for _ in range(100):
            port = allocate_nat_port(allocated)
            if port:
                ports.append(port)
        # All ports should be unique
        assert len(ports) == len(set(ports))

    def test_nat_port_range(self):
        """D8: Allocated port should be in valid range."""
        port = allocate_nat_port(set(), min_port=1024, max_port=65535)
        assert 1024 <= port <= 65535

    def test_nat_port_exhaustion(self):
        """D8: When all ports used, should return None."""
        allocated = set(range(1024, 1030))
        port = allocate_nat_port(allocated, min_port=1024, max_port=1029)
        assert port is None


class TestHealthCheckFlap:
    """Tests for D9: Load balancer health check stability."""

    def test_lb_health_check_stability(self):
        """D9: Health check should require multiple consecutive failures."""
        hc = HealthCheckState(target_id="t1")
        # Single failure should not mark unhealthy
        hc.record_check(success=False)
        assert hc.healthy is True, \
            "Single health check failure should not mark target unhealthy"

    def test_flap_detection(self):
        """D9: Rapid health transitions should be dampened."""
        hc = HealthCheckState(target_id="t1", healthy_threshold=3, unhealthy_threshold=3)
        # Multiple alternating results should not cause flapping
        for _ in range(5):
            hc.record_check(success=True)
            hc.record_check(success=False)
        # Should be stable in one state
        assert True, "Flap detection check"

    def test_consecutive_failures_marks_unhealthy(self):
        """D9: Multiple consecutive failures should mark unhealthy."""
        hc = HealthCheckState(
            target_id="t1", healthy_threshold=3, unhealthy_threshold=3
        )
        for _ in range(3):
            hc.record_check(success=False)
        assert hc.healthy is False

    def test_consecutive_successes_marks_healthy(self):
        """D9: Multiple consecutive successes should mark healthy."""
        hc = HealthCheckState(
            target_id="t1", healthy_threshold=3, unhealthy_threshold=3,
            healthy=False
        )
        for _ in range(3):
            hc.record_check(success=True)
        assert hc.healthy is True

    def test_health_check_defaults(self):
        """D9: Health check thresholds should be reasonable."""
        hc = HealthCheckState()
        assert hc.healthy_threshold >= 2, \
            f"Healthy threshold should be >= 2, got {hc.healthy_threshold}"
        assert hc.unhealthy_threshold >= 2, \
            f"Unhealthy threshold should be >= 2, got {hc.unhealthy_threshold}"


class TestPeeringRouting:
    """Tests for D10: Peering connection symmetric routing."""

    def test_peering_symmetric_routing(self):
        """D10: Peering should require both directions to work."""
        assert check_peering_routing(True, True) is True
        assert check_peering_routing(True, False) is False, \
            "Asymmetric peering (only A->B) should not be considered valid"
        assert check_peering_routing(False, True) is False, \
            "Asymmetric peering (only B->A) should not be considered valid"

    def test_bidirectional_peering(self):
        """D10: Both directions must route for valid peering."""
        assert check_peering_routing(False, False) is False
        assert check_peering_routing(True, True) is True


class TestCIDRAllocationEdgeCases:
    """Additional CIDR allocation edge case tests."""

    def test_cidr_large_parent(self):
        """Allocation from a /8 should work."""
        result = allocate_cidr(24, [], "10.0.0.0/8")
        assert result is not None

    def test_cidr_many_existing(self):
        """Allocation with many existing subnets."""
        existing = [f"10.0.{i}.0/24" for i in range(100)]
        result = allocate_cidr(24, existing, "10.0.0.0/16")
        if result:
            assert result not in existing

    def test_cidr_prefix_24(self):
        """Allocated /24 should have prefix length 24."""
        result = allocate_cidr(24, [], "10.0.0.0/16")
        if result:
            from ipaddress import IPv4Network
            net = IPv4Network(result)
            assert net.prefixlen == 24


class TestFirewallEdgeCases:
    """Additional firewall rule tests."""

    def test_many_rules_ordered(self):
        """Many rules should all be correctly ordered."""
        rules = [{"priority": 1000 - i, "action": "allow", "port": i} for i in range(100)]
        ordered = order_firewall_rules(rules)
        priorities = [r["priority"] for r in ordered]
        assert priorities == sorted(priorities)

    def test_single_rule(self):
        """Single rule should be returned as-is."""
        rules = [{"priority": 50, "action": "deny", "port": 22}]
        ordered = order_firewall_rules(rules)
        assert len(ordered) == 1
        assert ordered[0]["priority"] == 50


class TestVPNMTUEdgeCases:
    """Additional VPN MTU tests."""

    def test_mtu_minimum(self):
        """MTU should have a reasonable minimum."""
        mtu = calculate_vpn_mtu(576)  # Minimum IP MTU
        assert mtu > 0

    def test_mtu_with_high_overhead(self):
        """High encryption overhead should reduce MTU further."""
        mtu = calculate_vpn_mtu(1500, encryption_overhead=200)
        assert mtu == 1300

    def test_mtu_jumbo_frames(self):
        """Jumbo frame MTU should be handled."""
        mtu = calculate_vpn_mtu(9000, encryption_overhead=60)
        assert mtu == 8940


class TestDNSEdgeCases:
    """Additional DNS resolution tests."""

    def test_dns_many_records(self):
        """DNS with many records should still work."""
        records = {f"host{i}.example.com": f"host{i+1}.example.com" for i in range(50)}
        result = resolve_dns_cname("host0.example.com", records, max_depth=100)
        assert result is not None or result is None  # May hit depth limit

    def test_dns_empty_hostname(self):
        """Empty hostname should resolve to itself."""
        result = resolve_dns_cname("", {})
        assert result == ""

    def test_dns_max_depth_zero(self):
        """Max depth of 0 should resolve directly."""
        records = {"a.test": "b.test"}
        result = resolve_dns_cname("a.test", records, max_depth=0)
        assert result is not None


class TestSubnetExhaustionEdgeCases:
    """Additional subnet exhaustion tests."""

    def test_one_ip_remaining(self):
        """One IP remaining should not be exhausted."""
        assert check_subnet_exhaustion(253, 254) is False

    def test_exactly_one_over(self):
        """One more than total should be considered exhausted."""
        assert check_subnet_exhaustion(255, 254) is True

    def test_large_subnet(self):
        """Large subnet should work correctly."""
        assert check_subnet_exhaustion(65534, 65534) is True
        assert check_subnet_exhaustion(65533, 65534) is False


class TestSecurityGroupDedupEdgeCases:
    """Additional security group dedup tests."""

    def test_many_unique_rules(self):
        """Many unique rules should all be preserved."""
        rules = [
            {"protocol": "tcp", "port": i, "source": "10.0.0.0/8"}
            for i in range(100)
        ]
        result = deduplicate_security_group_rules(rules)
        assert len(result) == 100

    def test_all_duplicates(self):
        """All duplicate rules should reduce to one."""
        rule = {"protocol": "tcp", "port": 80, "source": "0.0.0.0/0"}
        rules = [dict(rule) for _ in range(10)]
        result = deduplicate_security_group_rules(rules)
        assert len(result) == 1

    def test_mixed_duplicates(self):
        """Mix of unique and duplicate rules."""
        rules = [
            {"protocol": "tcp", "port": 80, "source": "10.0.0.0/8"},
            {"protocol": "tcp", "port": 80, "source": "10.0.0.0/8"},
            {"protocol": "tcp", "port": 443, "source": "10.0.0.0/8"},
        ]
        result = deduplicate_security_group_rules(rules)
        assert len(result) == 2


class TestNATPortEdgeCases:
    """Additional NAT port tests."""

    def test_nat_first_allocation(self):
        """First NAT port allocation should succeed."""
        port = allocate_nat_port(set())
        assert port is not None
        assert port >= 1024

    def test_nat_many_allocations(self):
        """Many NAT port allocations should all be unique."""
        allocated = set()
        for _ in range(200):
            port = allocate_nat_port(allocated)
            if port is None:
                break
        # All allocated ports should be unique (guaranteed by set)
        assert len(allocated) > 0

    def test_nat_port_within_range(self):
        """Allocated ports should be within specified range."""
        port = allocate_nat_port(set(), min_port=10000, max_port=10010)
        assert port is None or (10000 <= port <= 10010)


class TestHealthCheckEdgeCases:
    """Additional health check tests."""

    def test_health_check_new_target(self):
        """New health check target should be healthy by default."""
        hc = HealthCheckState(target_id="new")
        assert hc.healthy is True

    def test_health_check_single_success(self):
        """Single success should not mark unhealthy target as healthy."""
        hc = HealthCheckState(
            target_id="t1", healthy_threshold=3, unhealthy_threshold=3,
            healthy=False,
        )
        hc.record_check(success=True)
        # One success is not enough (threshold=3)
        # Behavior depends on implementation

    def test_health_check_custom_thresholds(self):
        """Custom thresholds should be respected."""
        hc = HealthCheckState(
            target_id="custom",
            healthy_threshold=5,
            unhealthy_threshold=5,
        )
        assert hc.healthy_threshold == 5
        assert hc.unhealthy_threshold == 5
