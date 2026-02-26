"""
Violation checker using server policies.

SERVER RESPONSIBILITIES:
- Send initial MonitoringPolicy on agent connection
- Send updated MonitoringPolicy when rules change (via manager.update_policy())
- Handle incoming Event objects from agents
"""

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
    
    def check_port(self, port: int) -> dict | None:
        if not isinstance(port, int) or port < 0 or port > 65535 or port in self.policy.allowed_ports:
            return None
        return {"event_type": "port_violation", "description": f"Unallowed port: {port}"}

