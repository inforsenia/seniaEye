"""
Violation checker using server policies.

SERVER RESPONSIBILITIES:
- Send initial MonitoringPolicy on agent connection
- Send updated MonitoringPolicy when rules change (via manager.update_policy())
- Handle incoming Event objects from agents
"""

from typing import Optional
from agent.config.models import MonitoringPolicy
from agent.utils.logger import get_logger


logger = get_logger(__name__)


class ViolationChecker:
    def __init__(self, policy: MonitoringPolicy):
        self.policy = policy
    
    def update_policy(self, policy: MonitoringPolicy):
        self.policy = policy
        logger.info(f"Policy updated: domains={len(policy.blocked_domains)}, ips={len(policy.blocked_ips)}, ports={len(policy.allowed_ports)}")
    
    def check_dns(self, domain: str) -> dict | None:
        if not domain or domain.lower() not in {d.lower() for d in self.policy.blocked_domains}:
            return None
        return {"event_type": "dns_violation", "description": f"Blocked DNS: {domain}"}
    
    def check_ip(self, ip: str) -> dict | None:
        if not ip or ip not in self.policy.blocked_ips:
            return None
        return {"event_type": "ip_violation", "description": f"Blocked IP: {ip}"}
    
    def _find_port_rule(self, port: int):
        """Find PortRule for given port."""
        for rule in self.policy.allowed_ports:
            if rule.port == port:
                return rule
        return None
    
    def check_port(self, port: int, destination_ip: Optional[str] = None) -> dict | None:
        """Check if port is allowed, optionally considering destination IP."""
        # Validate port number
        if not isinstance(port, int) or port < 0 or port > 65535:
            return None
        
        # Check if port is in allowlist
        rule = self._find_port_rule(port)
        
        if not rule:
            return {
                "event_type": "port_violation",
                "description": f"Unallowed port: {port}"
            }
        
        # If destination IP specified, check destination whitelist
        if destination_ip and rule.allowed_destinations:
            if destination_ip not in rule.allowed_destinations:
                return {
                    "event_type": "port_violation",
                    "description": f"Unallowed destination {destination_ip} for port {port}"
                }
        
        return None  # Port is allowed

