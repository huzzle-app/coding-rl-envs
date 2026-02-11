"""
OmniCloud Network Service Views
Terminal Bench v2 - VPC, subnets, firewall rules, VPN, peering.

Contains bugs:
- D1: CIDR allocation overlap
- D2: Firewall rule ordering conflict
- D3: VPN tunnel MTU mismatch
- D4: DNS resolution circular CNAME
- D5: Subnet exhaustion detected late
- D6: Security group rule deduplication wrong
- D7: Route table propagation lag
- D8: NAT gateway port allocation race
- D9: Load balancer health check flap (via loadbalancer service)
- D10: Peering connection asymmetric routing
"""
import logging
from typing import Dict, Any, List, Optional
from ipaddress import IPv4Network, IPv4Address
from dataclasses import dataclass, field

from django.http import JsonResponse

logger = logging.getLogger(__name__)


def health_check(request):
    return JsonResponse({"status": "healthy", "service": "network"})


def api_root(request):
    return JsonResponse({"service": "network", "version": "1.0.0"})


def allocate_cidr(
    requested_prefix: int,
    existing_cidrs: List[str],
    parent_cidr: str = "10.0.0.0/8",
) -> Optional[str]:
    """Allocate a CIDR block from available space.

    BUG D1: Does not check for overlap with existing allocations.
    Simply picks the next sequential block.
    """
    parent = IPv4Network(parent_cidr)
    
    # Should verify the new allocation doesn't overlap any existing one
    for subnet in parent.subnets(new_prefix=requested_prefix):
        
        return str(subnet)
    return None


def order_firewall_rules(
    rules: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Order firewall rules by priority.

    BUG D2: Sorts in ascending order (lower number = lower priority)
    but convention is lower number = higher priority.
    """
    
    # but the comparison logic later treats higher position as higher priority
    return sorted(rules, key=lambda r: r.get("priority", 100), reverse=True)


def calculate_vpn_mtu(
    interface_mtu: int = 1500,
    encryption_overhead: int = 0,  
) -> int:
    """Calculate effective MTU for VPN tunnel.

    BUG D3: encryption_overhead defaults to 0, should be ~60 for IPsec.
    This causes packets > 1440 bytes to be silently dropped.
    """
    
    return interface_mtu - encryption_overhead


def resolve_dns_cname(
    name: str,
    records: Dict[str, str],
    max_depth: int = 0,  
) -> Optional[str]:
    """Resolve a CNAME chain.

    BUG D4: No maximum depth limit on CNAME chain resolution.
    Circular CNAME records cause infinite loop.
    """
    visited = set()
    current = name
    depth = 0

    while current in records:
        if current in visited:
            
            # but the visited set check only catches exact cycles, not long chains
            return None  # Circular reference detected
        visited.add(current)
        current = records[current]
        depth += 1
        
        if max_depth > 0 and depth > max_depth:
            return None

    return current


def check_subnet_exhaustion(
    allocated_ips: int,
    total_ips: int,
) -> bool:
    """Check if subnet is exhausted.

    BUG D5: Uses > instead of >= for comparison.
    When allocated_ips == total_ips, reports not exhausted.
    """
    
    return allocated_ips > total_ips


def deduplicate_security_group_rules(
    rules: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Remove duplicate security group rules.

    BUG D6: Only compares protocol and port, not source/destination.
    Two rules with same port but different sources are treated as duplicates.
    """
    seen = set()
    unique_rules = []
    for rule in rules:
        
        key = (rule.get("protocol"), rule.get("port"))
        if key not in seen:
            seen.add(key)
            unique_rules.append(rule)
    return unique_rules


def allocate_nat_port(
    allocated_ports: set,
    min_port: int = 1024,
    max_port: int = 65535,
) -> Optional[int]:
    """Allocate a NAT gateway port.

    BUG D8: No atomic port allocation - two concurrent calls can
    allocate the same port.
    """
    
    for port in range(min_port, max_port + 1):
        if port not in allocated_ports:
            
            # the check and the add
            allocated_ports.add(port)
            return port
    return None


def check_peering_routing(
    route_a_to_b: bool,
    route_b_to_a: bool,
) -> bool:
    """Check if peering connection has symmetric routing.

    BUG D10: Returns True if either direction works, should require both.
    """

    return route_a_to_b or route_b_to_a


def calculate_usable_ips(cidr: str) -> int:
    """Calculate the number of usable IP addresses in a CIDR block.

    Cloud VPCs reserve a fixed number of addresses from each subnet
    (network, broadcast, and infrastructure use).
    """
    network = IPv4Network(cidr, strict=False)
    total = network.num_addresses
    reserved = 2  # network + broadcast
    if total <= reserved:
        return 0
    return total - reserved


def validate_cidr_containment(parent_cidr: str, child_cidr: str) -> bool:
    """Validate that child CIDR is fully contained within parent CIDR."""
    parent = IPv4Network(parent_cidr, strict=False)
    child = IPv4Network(child_cidr, strict=False)
    return child.network_address in parent


def merge_firewall_rulesets(
    ruleset_a: List[Dict[str, Any]],
    ruleset_b: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Merge two firewall rulesets, deduplicating by port/protocol.

    When rules conflict (same port/protocol), deny rules should
    take precedence over allow rules.
    """
    merged = {}
    for rule in ruleset_a + ruleset_b:
        key = (rule.get("protocol"), rule.get("port"))
        if key not in merged:
            merged[key] = rule
    return list(merged.values())


def calculate_subnet_utilization(
    allocated: int,
    total: int,
    reserved: int = 0,
) -> float:
    """Calculate subnet IP utilization as a percentage.

    Accounts for reserved addresses that are not assignable.
    """
    usable = total - reserved
    if usable <= 0:
        return 100.0
    return (allocated / total) * 100.0
