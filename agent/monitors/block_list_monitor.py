"""Block list monitor - fetches and manages blocked domains/IPs from server."""

import threading
import json
import urllib.request
import urllib.error
from datetime import datetime
from typing import Dict, List, Optional
from agent.utils.logger import get_logger

logger = get_logger(__name__)


class BlockListMonitor:
    """Fetches and manages block list from server."""
    
    def __init__(self, server_url: str, fetch_interval: int = 300):
        """
        Initialize block list monitor.
        
        Args:
            server_url: Base URL of the server (e.g., http://127.0.0.1:1984)
            fetch_interval: Interval in seconds between fetches (default: 300 = 5 minutes)
        """
        self.server_url = server_url
        self.fetch_interval = fetch_interval
        self.block_list: Dict[str, List[str]] = {}
        self.last_timestamp: str = ""
        self.last_fetch: Optional[str] = None
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
    
    def _fetch_block_list(self) -> bool:
        """
        Fetch block list from server.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            url = f"{self.server_url}/api/block-list"
            request = urllib.request.Request(url)
            request.add_header('User-Agent', 'BlockListMonitor/1.0')
            
            with urllib.request.urlopen(request, timeout=10) as response:
                if response.status == 200:
                    data_bytes = response.read()
                    data = json.loads(data_bytes.decode('utf-8'))
                    
                    with self._lock:
                        self.block_list = data.get("domains", {})
                        self.last_timestamp = data.get("timestamp", "")
                        self.last_fetch = datetime.now().isoformat()
                    
                    total_domains = data.get("total_domains", 0)
                    total_ips = data.get("total_ips", 0)
                    
                    logger.info(
                        f"[BLOCK_LIST] Fetched block list from server\n"
                        f"  - Timestamp: {data.get('timestamp')}\n"
                        f"  - Total domains: {total_domains}\n"
                        f"  - Total IPs: {total_ips}\n"
                        f"  - Domains: {list(self.block_list.keys())}"
                    )
                    return True
                else:
                    logger.error(f"[BLOCK_LIST] Server returned status {response.status}")
                    return False
                    
        except urllib.error.URLError as e:
            logger.error(f"[BLOCK_LIST] Failed to connect to server: {e}")
            return False
        except urllib.error.HTTPError as e:
            logger.error(f"[BLOCK_LIST] HTTP error {e.code}: {e.reason}")
            return False
        except json.JSONDecodeError as e:
            logger.error(f"[BLOCK_LIST] Failed to parse JSON response: {e}")
            return False
        except Exception as e:
            logger.error(f"[BLOCK_LIST] Unexpected error fetching block list: {e}")
            return False
    
    def _run_fetch_loop(self):
        """Run the fetch loop in a separate thread."""
        try:
            while not self._stop_event.is_set():
                try:
                    self._fetch_block_list()
                except Exception as e:
                    logger.error(f"[BLOCK_LIST] Error in fetch loop: {e}")
                
                # Wait for next fetch or stop signal
                self._stop_event.wait(timeout=self.fetch_interval)
        except Exception as e:
            logger.error(f"[BLOCK_LIST] Fatal error in fetch loop: {e}")
    
    def start(self):
        """Start the monitor thread."""
        if self._thread and self._thread.is_alive():
            logger.warning("[BLOCK_LIST] Monitor already running")
            return
        
        logger.info(f"[BLOCK_LIST] Starting monitor (fetch interval: {self.fetch_interval}s)")
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_fetch_loop, daemon=True)
        self._thread.start()
        
        # Fetch immediately on startup
        try:
            self._fetch_block_list()
        except Exception as e:
            logger.error(f"[BLOCK_LIST] Failed initial fetch: {e}")
    
    def stop(self):
        """Stop the monitor thread."""
        logger.info("[BLOCK_LIST] Stopping monitor")
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
    
    def get_block_list(self) -> Dict[str, List[str]]:
        """
        Get current block list.
        
        Returns:
            Dictionary mapping domain to list of IPs
        """
        with self._lock:
            return self.block_list.copy()
    
    def get_blocked_ips(self) -> set:
        """
        Get all blocked IPs as a set.
        
        Returns:
            Set of all IP addresses from the block list
        """
        with self._lock:
            ips = set()
            for ip_list in self.block_list.values():
                ips.update(ip_list)
            return ips
    
    def is_ip_blocked(self, ip: str) -> bool:
        """
        Check if an IP is in the block list.
        
        Args:
            ip: IP address to check
            
        Returns:
            True if IP is blocked, False otherwise
        """
        return ip in self.get_blocked_ips()
    
    def is_domain_blocked(self, domain: str) -> bool:
        """
        Check if a domain is in the block list.
        
        Args:
            domain: Domain to check
            
        Returns:
            True if domain is blocked, False otherwise
        """
        if not domain:
            return False
        with self._lock:
            # Case-insensitive comparison for domains
            domain_lower = domain.lower()
            return any(d.lower() == domain_lower for d in self.block_list.keys())
