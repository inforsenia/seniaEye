"""Server policy models - received from server on connection."""

from pydantic import BaseModel
from typing import Set


class MonitoringPolicy(BaseModel):
    """Monitoring policies sent by server."""
    
    blocked_domains: Set[str] = set()
    blocked_ips: Set[str] = set()
    allowed_ports: Set[int] = set()
    
    class Config:
        frozen = True
