"""Agent entry point - initializes sender and monitors."""

import asyncio
import signal
import socket
from agent.sender.ws_sender import WSSender
from agent.monitors.manager import MonitorManager
from agent.utils.config import load_config
from agent.utils.machine_info import get_machine_name
from agent.utils.logger import get_logger

logger = get_logger(__name__)

_monitor_manager = None
_sender = None

def get_default_interface():
    """Detect the default network interface."""
    try:
        # Create a socket and connect to a remote address
        # This doesn't actually send anything, just determines routing
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        interface_ip = s.getsockname()[0]
        s.close()
        
        # Now get the interface name
        import subprocess
        result = subprocess.run(
            ["ip", "addr", "show"],
            capture_output=True,
            text=True
        )
        
        for line in result.stdout.split('\n'):
            if interface_ip in line:
                # Extract interface name (e.g., "eth0", "en0")
                parts = line.split()
                if parts:
                    return parts[-1] if parts[-1] not in ['brd'] else parts[0]
        
        # Fallback: try common interface names
        for iface in ["eth0", "en0", "wlan0", "docker0", "enp0s3"]:
            result = subprocess.run(
                ["ip", "addr", "show", iface],
                capture_output=True
            )
            if result.returncode == 0:
                return iface
    except Exception as e:
        logger.warning(f"Failed to detect interface: {e}")
    
    return None

def setup_signal_handlers():
    """Handle graceful shutdown."""
    def signal_handler(signum, frame):
        logger.info(f"Signal {signum} received, shutting down...")
        if _monitor_manager:
            _monitor_manager.stop()
        raise KeyboardInterrupt()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

async def main():
    global _monitor_manager, _sender
    
    try:
        config = load_config("agent/config/default.conf")
        machine_name = config.machine_name or get_machine_name()
        logger.info(f"Machine: {machine_name}")
        
        _sender = WSSender()
        asyncio.create_task(_sender.run())
        
        # Extract server URL from ws_url (e.g., ws://127.0.0.1:8000/ws/events -> http://127.0.0.1:8000)
        server_url = "http://localhost:8000"
        if hasattr(config, 'ws_url') and config.ws_url:
            # Convert ws:// or wss:// to http:// or https://
            ws_url = config.ws_url
            if ws_url.startswith("wss://"):
                server_url = "https://" + ws_url[6:].split('/')[0]
            elif ws_url.startswith("ws://"):
                server_url = "http://" + ws_url[5:].split('/')[0]
        
        _monitor_manager = MonitorManager(
            event_callback=_sender.add_event,
            machine_name=machine_name,
            interface=get_default_interface(),
            server_url=server_url
        )
        
        logger.info("Starting monitors...")
        _monitor_manager.start()
        
        while True:
            await asyncio.sleep(1)
    
    except KeyboardInterrupt:
        logger.info("Shutting down")
        if _monitor_manager:
            _monitor_manager.stop()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        if _monitor_manager:
            _monitor_manager.stop()
        raise

if __name__ == "__main__":
    setup_signal_handlers()
    asyncio.run(main())