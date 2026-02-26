"""Machine identification utilities."""

import os
import socket

def get_machine_name() -> str:
    """Get machine identifier from env var or hostname."""
    machine_name = os.getenv("MACHINE_NAME")
    if machine_name:
        return machine_name
    
    try:
        return socket.gethostname()
    except Exception:
        return "UNKNOWN_MACHINE"

