"""Configuration loader for agent server settings."""

import os
import yaml
from pathlib import Path
from agent.utils.logger import get_logger


logger = get_logger(__name__)


class ConfigLoader:
    """Load agent configuration (server connection only)."""
    
    def __init__(self, config_file: str = "agent/config/default.yaml"):
        self.config_file = Path(config_file)
        self.config = {}
        
        self.base_url = "127.0.0.1:1984"
        self.server_url = "ws://127.0.0.1:1984/ws/events"
        self.retry_delay = 30
        self.machine_name = ""
        self.log_level = "INFO"
        
        self._load_config()
    
    def _load_config(self):
        """Load configuration file."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    self.config = yaml.safe_load(f) or {}
            except Exception as e:
                logger.warning(f"Config load failed: {e}")
                self.config = {}
        
        # Load server settings
        server_config = self.config.get("server", {})
        base_url = server_config.get("base_url", "http://127.0.0.1:1984")
        
        if base_url:
            host_port = base_url.split("://")[-1] if "://" in base_url else base_url
            self.base_url = base_url
            self.server_url = f"ws://{host_port}/ws/events"
        
        self.retry_delay = server_config.get("retry_delay", self.retry_delay)
        
        # Load agent settings
        agent_config = self.config.get("agent", {})
        self.machine_name = agent_config.get("machine_name", "").strip() or os.getenv("MACHINE_NAME", "")
        self.log_level = agent_config.get("log_level", self.log_level)


def load_config(config_file: str = "agent/config/default.yaml") -> ConfigLoader:
    return ConfigLoader(config_file)

