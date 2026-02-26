"""Configuration loader for agent server settings."""

import os
import configparser
from pathlib import Path
from agent.utils.logger import get_logger


logger = get_logger(__name__)


class ConfigLoader:
    """Load agent configuration (server connection only)."""
    
    def __init__(self, config_file: str = "agent/config/default.conf"):
        self.config_file = Path(config_file)
        self.config = configparser.ConfigParser()
        
        self.server_url = "ws://127.0.0.1:8000/ws/events"
        self.retry_delay = 30
        self.machine_name = ""
        self.log_level = "INFO"
        
        self._load_config()
    
    def _load_config(self):
        """Load configuration file."""
        if self.config_file.exists():
            try:
                self.config.read(self.config_file)
            except Exception as e:
                logger.warning(f"Config load failed: {e}")
        
        self.server_url = self.config.get("server", "ws_url", fallback=self.server_url)
        self.retry_delay = self.config.getint("server", "retry_delay", fallback=self.retry_delay)
        self.machine_name = self.config.get("agent", "machine_name", fallback="").strip() or \
                            os.getenv("MACHINE_NAME", "")
        self.log_level = self.config.get("agent", "log_level", fallback=self.log_level)


def load_config(config_file: str = "agent/config/default.conf") -> ConfigLoader:
    return ConfigLoader(config_file)

