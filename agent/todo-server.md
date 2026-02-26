### Server Policy Format

```json
{
  "blocked_domains": [
    "malicious.com", 
    "ad.example.com"
  ],
  "blocked_ips": [
    "192.168.1.100", 
    "10.0.0.50"
  ],
  "allowed_ports": [
    22, 53, 80, 443, 8080
  ]
}

```