"""Local network utilities - Get local machine IP addresses and network info."""

import socket
import ipaddress
from typing import Set


def get_local_ips() -> Set[str]:
    """
    Get all local IP addresses of the machine.
    
    Returns:
        Set of IP addresses (both IPv4 and IPv6) assigned to local interfaces.
        Includes loopback addresses (127.0.0.1, ::1).
    """
    local_ips = set()
    
    try:
        # Get hostname
        hostname = socket.gethostname()
        
        # Get all IP addresses for this hostname
        try:
            addr_info = socket.getaddrinfo(hostname, None)
            for family, type_, proto, canonname, sockaddr in addr_info:
                ip = sockaddr[0]
                if ip not in local_ips:
                    local_ips.add(ip)
        except socket.gaierror:
            pass
    except Exception:
        pass
    
    # Always include loopback addresses
    local_ips.add("127.0.0.1")
    local_ips.add("::1")
    
    # Add localhost
    try:
        local_ips.add(socket.gethostbyname("localhost"))
    except socket.gaierror:
        pass
    
    return local_ips


def is_local_ip(ip: str) -> bool:
    """
    Check if an IP address is local to the machine.
    
    Args:
        ip: IP address to check
    
    Returns:
        True if the IP is a local address, False otherwise
    """
    try:
        # First, check common local ranges
        ip_obj = ipaddress.ip_address(ip)
        
        # Check if it's loopback (127.x.x.x or ::1)
        if ip_obj.is_loopback:
            return True
        
        # Check if it's in local machine's IPs
        local_ips = get_local_ips()
        return ip in local_ips
    except ValueError:
        # Invalid IP address
        return False


def is_external_ip(ip: str) -> bool:
    """
    Check if an IP address is external to the machine (not local).
    
    Args:
        ip: IP address to check
    
    Returns:
        True if the IP is external, False if it's local
    """
    return not is_local_ip(ip)
