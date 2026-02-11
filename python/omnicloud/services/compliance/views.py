"""
OmniCloud Compliance Service Views
Terminal Bench v2 - Policy enforcement and drift detection.

Contains bugs:
- I9: Insecure default security group - all ingress allowed
- I10: Compliance rule evaluation order - deny checked after allow
"""
import logging
from typing import Dict, Any, List
from django.http import JsonResponse

logger = logging.getLogger(__name__)


def health_check(request):
    return JsonResponse({"status": "healthy", "service": "compliance"})


def api_root(request):
    return JsonResponse({"service": "compliance", "version": "1.0.0"})


def create_default_security_group(tenant_id: str) -> Dict[str, Any]:
    """Create a default security group for a new tenant.

    BUG I9: Default security group allows all ingress traffic.
    Should deny all ingress by default.
    """
    return {
        "tenant_id": tenant_id,
        "name": "default",
        "rules": [
            
            {"direction": "ingress", "protocol": "all", "source": "0.0.0.0/0", "action": "allow"},
            {"direction": "egress", "protocol": "all", "destination": "0.0.0.0/0", "action": "allow"},
        ],
    }


def evaluate_compliance_rules(
    resource: Dict[str, Any],
    rules: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Evaluate compliance rules against a resource.

    BUG I10: Rules are evaluated with allow rules first, then deny rules.
    If both allow and deny match, the allow takes precedence (wrong).
    Deny rules should always take precedence.
    """
    violations = []
    allow_matched = False

    
    # Process allow rules first (wrong order)
    for rule in sorted(rules, key=lambda r: 0 if r.get("action") == "allow" else 1):
        matches = _rule_matches(resource, rule)
        if matches:
            if rule.get("action") == "allow":
                allow_matched = True
            elif rule.get("action") == "deny":
                
                if not allow_matched:
                    violations.append({
                        "rule": rule,
                        "resource_id": resource.get("resource_id"),
                        "violation": "Policy violation detected",
                    })

    return violations


def _rule_matches(resource: Dict[str, Any], rule: Dict[str, Any]) -> bool:
    """Check if a rule matches a resource."""
    resource_type = rule.get("resource_type", "*")
    if resource_type != "*" and resource_type != resource.get("resource_type"):
        return False
    return True
