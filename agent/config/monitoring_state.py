"""Centralized monitoring state management."""

import threading
from typing import Callable, List

class MonitoringState:
    """Thread-safe monitoring state controller."""
    
    def __init__(self):
        self._lock = threading.Lock()
        self._is_monitoring = False
        self._callbacks: List[Callable[[bool], None]] = []
    
    def set_monitoring(self, enabled: bool):
        """Set monitoring state and notify callbacks."""
        with self._lock:
            if self._is_monitoring == enabled:
                return  # No state change
            
            self._is_monitoring = enabled
            # Notify all registered callbacks
            for callback in self._callbacks:
                try:
                    callback(enabled)
                except Exception as e:
                    print(f"Error in monitoring state callback: {e}")
    
    def is_monitoring(self) -> bool:
        """Check if monitoring is active."""
        with self._lock:
            return self._is_monitoring
    
    def register_callback(self, callback: Callable[[bool], None]):
        """Register a callback to be called when monitoring state changes.
        
        Args:
            callback: Function that takes a boolean (True = started, False = stopped)
        """
        with self._lock:
            if callback not in self._callbacks:
                self._callbacks.append(callback)
    
    def unregister_callback(self, callback: Callable[[bool], None]):
        """Unregister a callback."""
        with self._lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)


# Global singleton instance
_global_state = MonitoringState()

def get_monitoring_state() -> MonitoringState:
    """Get the global monitoring state instance."""
    return _global_state
