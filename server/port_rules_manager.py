"""Port Rules Manager - manages and validates allowed port rules."""

import yaml
import logging
from pathlib import Path
from ipaddress import ip_address, ip_network, AddressValueError
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class SourceRule:
    """Represents a source rule (subnet, IP, localhost, or any)."""
    
    def __init__(self, type_: str, value: str):
        self.type = type_  # "subnet", "ip", "localhost", "any"
        self.value = value
    
    def to_dict(self) -> dict:
        return {"type": self.type, "value": self.value}


class PortRule:
    """Represents a port rule with allowed sources."""
    
    def __init__(self, port: int, protocol: str, description: str, allowed_sources: List[SourceRule]):
        self.port = port
        self.protocol = protocol  # "tcp" or "udp"
        self.description = description
        self.allowed_sources = allowed_sources
    
    def to_dict(self) -> dict:
        return {
            "port": self.port,
            "protocol": self.protocol,
            "description": self.description,
            "allowed_sources": [source.to_dict() for source in self.allowed_sources]
        }


class PortRulesManager:
    """Manages allowed port and source rules."""
    
    def __init__(self, config_file: str = "server/allowed_ports_config.yaml"):
        """Initialize rules manager and load rules from YAML file."""
        self.rules: Dict[int, PortRule] = {}  # port → PortRule
        self.config_file = config_file
        self.load_rules()
    
    def load_rules(self) -> bool:
        """Load port rules from YAML file."""
        config_path = Path(self.config_file)
        
        if not config_path.exists():
            logger.warning(f"[PORT_RULES] Config file not found: {self.config_file}")
            return False
        
        try:
            with open(config_path, 'r') as f:
                data = yaml.safe_load(f)
            
            if not data or "rules" not in data:
                logger.warning("[PORT_RULES] No rules found in config file")
                return False
            
            self.rules = {}
            rules_list = data["rules"]
            
            logger.info(f"[BOOT] Loading port rules from {self.config_file}")
            
            for rule_data in rules_list:
                try:
                    port = rule_data.get("port")
                    protocol = rule_data.get("protocol", "tcp").lower()
                    description = rule_data.get("description", f"Port {port}")
                    sources_data = rule_data.get("allowed_sources", [])
                    
                    # Validate port
                    if not isinstance(port, int) or port < 1 or port > 65535:
                        logger.warning(f"[PORT_RULES] Invalid port {port}, skipping")
                        continue
                    
                    # Validate protocol
                    if protocol not in ["tcp", "udp"]:
                        logger.warning(f"[PORT_RULES] Invalid protocol '{protocol}' for port {port}, skipping")
                        continue
                    
                    # Check for duplicate ports
                    if port in self.rules:
                        logger.warning(f"[PORT_RULES] Duplicate port {port}, using new definition")
                    
                    # Parse allowed sources
                    allowed_sources = []
                    for source_data in sources_data:
                        source_type = source_data.get("type")
                        source_value = source_data.get("value")
                        
                        # Validate source
                        if not self._validate_source(source_type, source_value):
                            logger.warning(f"[PORT_RULES] Invalid source for port {port}: {source_type}={source_value}, skipping")
                            continue
                        
                        allowed_sources.append(SourceRule(source_type, source_value))
                    
                    if not allowed_sources and sources_data:
                        logger.warning(f"[PORT_RULES] Port {port} has invalid sources, skipping rule")
                        continue
                    
                    # Create and store rule
                    rule = PortRule(port, protocol, description, allowed_sources)
                    self.rules[port] = rule
                    
                    source_count = len(allowed_sources)
                    if source_count == 0:
                        source_desc = "No sources"
                    elif any(s.type == "any" for s in allowed_sources):
                        source_desc = "Allow all"
                    else:
                        source_desc = f"{source_count} allowed sources"
                    
                    logger.info(f"[BOOT] Port {port:5d} ({protocol.upper()}): {source_desc} - {description}")
                
                except Exception as e:
                    logger.error(f"[PORT_RULES] Error parsing rule: {e}")
                    continue
            
            logger.info(f"[BOOT] Loaded {len(self.rules)} port rule(s) successfully")
            return True
        
        except yaml.YAMLError as e:
            logger.error(f"[PORT_RULES] YAML parsing error: {e}")
            return False
        except Exception as e:
            logger.error(f"[PORT_RULES] Failed to load rules: {e}")
            return False
    
    def _validate_source(self, source_type: str, source_value: str) -> bool:
        """Validate a source rule."""
        if source_type == "any":
            return source_value == "0.0.0.0/0" or source_value == "::/0"
        elif source_type == "ip":
            try:
                ip_address(source_value)
                return True
            except (AddressValueError, ValueError):
                return False
        elif source_type == "subnet":
            try:
                ip_network(source_value, strict=False)
                return True
            except (AddressValueError, ValueError):
                return False
        elif source_type == "localhost":
            return source_value in ["127.0.0.1", "::1"]
        return False
    
    def _matches_source_rule(self, source_ip: str, rule: SourceRule) -> bool:
        """Check if source IP matches a source rule."""
        try:
            if rule.type == "any":
                return True
            
            elif rule.type == "ip":
                return source_ip == rule.value
            
            elif rule.type == "subnet":
                source_addr = ip_address(source_ip)
                subnet = ip_network(rule.value, strict=False)
                return source_addr in subnet
            
            elif rule.type == "localhost":
                return source_ip in ["127.0.0.1", "::1"]
        
        except (AddressValueError, ValueError):
            logger.debug(f"Invalid IP address: {source_ip}")
            return False
        
        return False
    
    def is_port_allowed(self, port: int, source_ip: str, protocol: str = "tcp") -> Dict:
        """
        Check if port is allowed from source.
        
        Args:
            port: Destination port
            source_ip: Source IP address
            protocol: Protocol (tcp or udp)
        
        Returns:
            {
                "allowed": bool,
                "port": int,
                "source_ip": str,
                "protocol": str,
                "matched_rule": PortRule or None,
                "reason": str
            }
        """
        protocol = protocol.lower()
        
        # Get rule for this port
        rule = self.get_port_rule(port)
        
        if not rule:
            return {
                "allowed": False,
                "port": port,
                "source_ip": source_ip,
                "protocol": protocol,
                "matched_rule": None,
                "reason": "Port not in whitelist"
            }
        
        # Check if protocol matches
        if rule.protocol != protocol:
            return {
                "allowed": False,
                "port": port,
                "source_ip": source_ip,
                "protocol": protocol,
                "matched_rule": rule,
                "reason": f"Protocol mismatch (rule is {rule.protocol})"
            }
        
        # Check if source matches any allowed sources
        for source_rule in rule.allowed_sources:
            if self._matches_source_rule(source_ip, source_rule):
                return {
                    "allowed": True,
                    "port": port,
                    "source_ip": source_ip,
                    "protocol": protocol,
                    "matched_rule": rule,
                    "reason": "Allowed by rule"
                }
        
        return {
            "allowed": False,
            "port": port,
            "source_ip": source_ip,
            "protocol": protocol,
            "matched_rule": rule,
            "reason": f"Source not in allowed list for port {port}"
        }
    
    def is_source_allowed_for_port(self, port: int, source_ip: str, protocol: str = "tcp") -> bool:
        """Quick check if source is allowed for port."""
        result = self.is_port_allowed(port, source_ip, protocol)
        return result["allowed"]
    
    def get_port_rule(self, port: int) -> Optional[PortRule]:
        """Get rule for specific port."""
        return self.rules.get(port)
    
    def get_all_rules(self) -> List[PortRule]:
        """Return all rules as list."""
        return list(self.rules.values())
    
    def get_all_rules_dict(self) -> Dict[int, dict]:
        """Return all rules as dictionary of dicts."""
        return {port: rule.to_dict() for port, rule in self.rules.items()}
