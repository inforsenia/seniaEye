#!/usr/bin/env python3
"""Test script to verify InterfaceMonitor functionality."""

import time
import pyudev
from agent.utils.logger import get_logger

logger = get_logger(__name__)

def test_pyudev_basic():
    """Test basic pyudev initialization."""
    print("\n=== Testing pyudev basic functionality ===")
    try:
        context = pyudev.Context()
        print(f"✓ pyudev Context created")
        
        monitor = pyudev.Monitor.from_netlink(context)
        print(f"✓ pyudev Monitor created from netlink")
        
        monitor.filter_by(subsystem="net")
        print(f"✓ Filter set to subsystem='net'")
        
        return True
    except Exception as e:
        print(f"✗ pyudev initialization failed: {e}")
        print("  Note: This might require root/sudo permissions")
        return False

def test_udev_enumeration():
    """Test enumerating existing network interfaces."""
    print("\n=== Testing udev enumeration (no monitoring, just list) ===")
    try:
        context = pyudev.Context()
        for device in context.list_devices(subsystem='net'):
            print(f"  - {device.get('INTERFACE', device.sys_name)} (Driver: {device.get('DRIVER', 'unknown')})")
        print("✓ Successfully enumerated network interfaces")
        return True
    except Exception as e:
        print(f"✗ Enumeration failed: {e}")
        return False

def test_monitor_with_timeout():
    """Test monitoring for 30 seconds."""
    print("\n=== Testing event monitoring (30 second timeout) ===")
    print("Connect/disconnect your USB WiFi device to test...")
    
    try:
        context = pyudev.Context()
        monitor = pyudev.Monitor.from_netlink(context)
        monitor.filter_by(subsystem='net')
        
        observer = pyudev.MonitorObserver(monitor, callback=_handle_event)
        observer.start()
        print("✓ Monitor observer started")
        print("  Waiting for events... (Ctrl+C to stop)")
        
        try:
            time.sleep(30)
        except KeyboardInterrupt:
            print("\n  (Stopped by user)")
        finally:
            observer.stop()
            print("✓ Monitor observer stopped")
        
        return True
    except Exception as e:
        print(f"✗ Monitoring failed: {e}")
        print("  This usually means you need root/sudo permissions")
        return False

def _handle_event(device):
    """Callback for udev events."""
    action = device.action
    interface = device.get('INTERFACE', device.sys_name)
    print(f"  EVENT: {action:6} - {interface:10} (Driver: {device.get('DRIVER', 'unknown'):15}) Path: {device.sys_path}")

if __name__ == "__main__":
    print("=" * 60)
    print("InterfaceMonitor Test Suite")
    print("=" * 60)
    
    print("\nIMPORTANT: Some tests may require 'sudo' permissions!")
    print("If tests fail, try running: sudo python3 test_interface_monitor.py")
    
    # Run tests
    basic_ok = test_pyudev_basic()
    enum_ok = test_udev_enumeration()
    
    if basic_ok:
        test_monitor_with_timeout()
    else:
        print("\n⚠ Basic tests failed - cannot proceed with monitoring test")
        print("\nTry running with sudo:")
        print("  sudo python3 test_interface_monitor.py")
    
    print("\n" + "=" * 60)
    print("Test complete")
    print("=" * 60)
