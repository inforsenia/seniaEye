"""Port Rules Monitor - fetches and caches port rules from server."""

import threading
import json
import time
from typing import Dict, Optional, Callable
from agent.utils.logger import get_logger

logger = get_logger(__name__)


class PortRulesMonitor:
    """Monitors and syncs port rules from server."""
    
    def __init__(self, server_url: str = "http://127.0.0.1:1984", 
                 sync_interval: int = 600):
        """
        Initialize port rules monitor.
        
        Args:
            server_url: Base URL of the server (e.g., http://127.0.0.1:1984)
            sync_interval: Interval in seconds to sync rules from server (default 10 minutes)
        """
        self.server_url = server_url.rstrip('/')
        self.sync_interval = sync_interval
        self.rules: Dict = {}  # port → rule dict
        self.last_sync: Optional[float] = None
        self.thread: Optional[threading.Thread] = None
        self.running = False
        self.lock = threading.Lock()
    
    def start(self):
        """Start the port rules monitor thread."""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        logger.info("[PORT_RULES] Monitor started")
        
        # Fetch rules immediately on first start
        self.sync_rules()
    
    def stop(self):
        """Stop the port rules monitor thread."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("[PORT_RULES] Monitor stopped")
    
    def _run(self):
        """Main run loop for periodic syncing."""
        while self.running:
            try:
                time.sleep(self.sync_interval)
                if self.running:
                    self.sync_rules()
            except Exception as e:
                logger.error(f"[PORT_RULES] Monitor error: {e}")
    
    def sync_rules(self) -> bool:
        """Fetch port rules from server."""
        try:
            # Import requests here to avoid circular dependency
            import requests
            
            url = f"{self.server_url}/api/port-rules"
            response = requests.get(url, timeout=5)
            
            if response.status_code != 200:
                logger.error(f"[PORT_RULES] Failed to fetch rules: HTTP {response.status_code}")
                return False
            
            data = response.json()
            
            with self.lock:
                self.rules = {}
                for rule in data.get("rules", []):
                    port = rule.get("port")
                    if port:
                        self.rules[port] = rule
                
                self.last_sync = time.time()
            
            total_rules = len(self.rules)
            logger.info(f"[PORT_RULES] Synced {total_rules} rule(s) from server")
            
            return True
        
        except requests.exceptions.RequestException as e:
            logger.warning(f"[PORT_RULES] Failed to reach server: {e}")
            return False
        except json.JSONDecodeError as e:
            logger.error(f"[PORT_RULES] Failed to parse response: {e}")
            return False
        except Exception as e:
            logger.error(f"[PORT_RULES] Sync error: {e}")
            return False
    
    def get_rule(self, port: int) -> Optional[Dict]:
        """Get rule for a specific port."""
        with self.lock:
            return self.rules.get(port)
    
    def get_all_rules(self) -> Dict:
        """Get all rules."""
        with self.lock:
            return dict(self.rules)
    
    def is_port_allowed(self, port: int, source_ip: str, protocol: str = "tcp") -> bool:
        """
        Check if port is allowed from source using locally cached rules.
        
        Args:
            port: Destination port
            source_ip: Source IP address
            protocol: Protocol (tcp or udp)
        
        Returns:
            True if allowed, False otherwise
        """
        from ipaddress import ip_address, ip_network, AddressValueError
        
        with self.lock:
            rule = self.rules.get(port)
        
        if not rule:
            # No rule = not allowed (whitelist model)
            return False
        
        # Check protocol
        if rule.get("protocol", "tcp").lower() != protocol.lower():
            return False
        
        # Check if source matches any allowed sources
        allowed_sources = rule.get("allowed_sources", [])
        
        for source_rule in allowed_sources:
            source_type = source_rule.get("type")
            source_value = source_rule.get("value")
            
            try:
                if source_type == "any":
                    return True
                
                elif source_type == "ip":
                    if source_ip == source_value:
                        return True
                
                elif source_type == "subnet":
                    source_addr = ip_address(source_ip)
                    subnet = ip_network(source_value, strict=False)
                    if source_addr in subnet:
                        return True
                
                elif source_type == "localhost":
                    if source_ip in ["127.0.0.1", "::1"]:
                        return True
            
            except (AddressValueError, ValueError):
                logger.debug(f"Invalid IP in rule check: {source_ip}")
                continue
        
        return False
    
    def get_sync_status(self) -> Dict:
        """Get synchronization status."""
        return {
            "synced": self.last_sync is not None,
            "last_sync": self.last_sync,
            "total_rules": len(self.rules),
            "running": self.running
        }
