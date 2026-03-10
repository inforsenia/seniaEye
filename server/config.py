"""Server configuration loader - reads from server/config.yaml."""

import yaml
from pathlib import Path
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


def load_server_config() -> Dict[str, Any]:
    """Load server configuration from config.yaml."""
    config_path = Path(__file__).parent / "config.yaml"
    
    if not config_path.exists():
        logger.error(f"Configuration file not found: {config_path}")
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        logger.info(f"Configuration loaded successfully from {config_path}")
        return config
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        raise


def get_server_address() -> tuple[str, int]:
    """Get server host and port from configuration."""
    config = load_server_config()
    server_config = config.get('server', {})
    host = server_config.get('host', '0.0.0.0')
    port = server_config.get('port', 1984)
    return host, port


def get_server_url() -> str:
    """Get the base URL of the server."""
    config = load_server_config()
    server_config = config.get('server', {})
    return server_config.get('base_url', 'http://127.0.0.1:1984')


def get_websocket_url() -> str:
    """Get the WebSocket URL."""
    config = load_server_config()
    server_config = config.get('server', {})
    websocket_config = server_config.get('websocket', {})
    return websocket_config.get('url', 'ws://127.0.0.1:1984/ws/events')
