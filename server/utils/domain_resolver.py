"""Domain to IP resolver using dig command."""

import subprocess
import logging
from typing import Dict, List
from datetime import datetime

logger = logging.getLogger(__name__)


class DomainResolver:
    """Resolves domains to IP addresses using dig command."""
    
    def __init__(self):
        """Initialize resolver."""
        self.cache: Dict[str, List[str]] = {}
        self.timestamp: str = ""
    
    def resolve_domain(self, domain: str) -> List[str]:
        """
        Resolve a single domain to list of IPs.
        
        Args:
            domain: Domain name to resolve
            
        Returns:
            List of IP addresses, empty list if resolution fails
        """
        try:
            result = subprocess.run(
                ['dig', domain, '+short'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                logger.warning(f"dig command failed for {domain} with return code {result.returncode}")
                return []
            
            # Filter out CNAME entries and empty lines, keep only IPs
            ips = []
            for line in result.stdout.strip().split('\n'):
                line = line.strip()
                if not line:
                    continue
                # Skip CNAME and other non-IP responses
                if not any(c.isdigit() for c in line):
                    continue
                # Basic IP validation - if it contains dots and is not CNAME
                if '.' in line and not line.endswith('.'):
                    ips.append(line)
            
            if ips:
                logger.info(f"Successfully resolved {domain} to {len(ips)} IP(s)")
            else:
                logger.warning(f"No IP addresses found for domain {domain}")
            
            return ips
            
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout resolving domain {domain}")
            return []
        except FileNotFoundError:
            logger.error("dig command not found. Please install dnsutils/bind-utils")
            raise RuntimeError("dig command not available")
        except Exception as e:
            logger.error(f"Failed to resolve {domain}: {e}")
            return []
    
    def resolve_domains(self, domain_list: List[str]) -> Dict[str, List[str]]:
        """
        Resolve multiple domains to IPs.
        
        Args:
            domain_list: List of domain names
            
        Returns:
            Dictionary mapping domain to list of IPs
        """
        self.timestamp = datetime.now().isoformat()
        self.cache = {}
        
        logger.info(f"Starting resolution of {len(domain_list)} domain(s)")
        
        for domain in domain_list:
            domain = domain.strip()
            if not domain:
                continue
            
            ips = self.resolve_domain(domain)
            self.cache[domain] = ips
        
        total_ips = sum(len(ips) for ips in self.cache.values())
        logger.info(f"Resolution complete: {len(self.cache)} domains, {total_ips} total IPs")
        
        return self.cache
    
    def get_cache(self) -> Dict[str, List[str]]:
        """Get cached resolver data."""
        return self.cache
    
    def get_timestamp(self) -> str:
        """Get timestamp of last resolution."""
        return self.timestamp
