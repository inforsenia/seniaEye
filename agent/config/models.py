"""Server policy models - received from server on connection."""

from pydantic import BaseModel
from typing import Set, Optional, List


class PortRule(BaseModel):
    """Port rule with optional destination IP whitelist."""
    port: int
    allowed_destinations: Optional[List[str]] = None  # If None, port allowed to any destination


class MonitoringPolicy(BaseModel):
    """Monitoring policies sent by server."""
    
    blocked_domains: Set[str] = set()
    blocked_ips: Set[str] = set()
    allowed_ports: List[PortRule] = []
    
    class Config:
        frozen = False
