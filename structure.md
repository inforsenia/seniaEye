# Project Structure Plan

Here's a clean, well-organized Python project structure for this exam monitoring system:

```
exam-monitor/
├── README.md
├── pyproject.toml                  # Project metadata & dependencies (use uv or pip)
├── .env.example
│
├── agent/                          # Runs on each classroom computer
│   ├── __init__.py
│   ├── main.py                     # Entry point, orchestrates all monitors
│   ├── config.py                   # Load config (server URL, blacklists, allowed ports…)
│   │
│   ├── monitors/                   # Each monitoring concern is isolated
│   │   ├── __init__.py
│   │   ├── port_monitor.py         # Watches outgoing connections / ports
│   │   ├── dns_monitor.py          # Sniffs DNS queries, checks blacklist
│   │   ├── ip_monitor.py           # Compares destination IPs vs resolved blacklist IPs
│   │   └── interface_monitor.py    # Detects new network interfaces (USB adapters, etc.)
│   │
│   ├── blacklist/
│   │   ├── __init__.py
│   │   ├── loader.py               # Load/reload blacklist from file or server
│   │   └── resolver.py             # Dynamically resolve blacklist domains → IPs
│   │
│   ├── events/
│   │   ├── __init__.py
│   │   ├── models.py               # Event dataclasses/Pydantic models
│   │   └── queue.py                # Local in-memory queue before sending
│   │
│   └── sender/
│       ├── __init__.py
│       └── http_sender.py          # Periodic POST of events to central server
│
├── server/                         # Central server
│   ├── __init__.py
│   ├── main.py                     # FastAPI app entry point
│   ├── config.py
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── events.py           # POST /events  (receives agent data)
│   │   │   ├── machines.py         # GET  /machines (list of monitored PCs)
│   │   │   └── blacklist.py        # GET/PUT /blacklist (manage blacklist remotely)
│   │   └── deps.py                 # Shared FastAPI dependencies
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── event.py                # SQLAlchemy / Pydantic event models
│   │   └── machine.py
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── database.py             # SQLite (dev) / PostgreSQL (prod) setup
│   │   └── migrations/             # Alembic migrations
│   │
│   └── ws/
│       ├── __init__.py
│       └── broadcaster.py          # WebSocket broadcast for real-time dashboard
│
├── dashboard/                      # Supervisor web UI (can be a separate repo)
│   ├── index.html
│   ├── app.js                      # Connects via WebSocket to server
│   └── style.css
│
└── shared/                         # Code shared between agent and server
    ├── __init__.py
    ├── schemas.py                  # Pydantic models for the API contract
    └── constants.py                # Allowed ports, default config values
```

---

## Key Technology Choices

**Agent side** — needs elevated privileges on Ubuntu 24 to sniff packets:

| Need | Library |
|---|---|
| Packet capture (DNS/ports) | `scapy` or `pyshark` (wraps tshark) |
| Interface monitoring | `psutil` (watch `net_if_stats`) or `pyroute2` |
| HTTP sender | `httpx` (async) |
| Config | `pydantic-settings` + a YAML/TOML file |

**Server side:**

| Need | Library |
|---|---|
| Web framework | `FastAPI` |
| Database ORM | `SQLAlchemy` + `alembic` |
| Real-time push | `FastAPI` WebSockets |
| DB | SQLite for dev, PostgreSQL for prod |

---

## Deployment on Ubuntu 24

The agent needs to run as a **systemd service** with root or `CAP_NET_RAW` capability for packet capture. A minimal unit file:

```ini
# /etc/systemd/system/exam-agent.service
[Unit]
Description=Exam Monitor Agent
After=network.target

[Service]
ExecStart=/opt/exam-monitor/venv/bin/python -m agent.main
WorkingDirectory=/opt/exam-monitor
Restart=always
User=root          # or a dedicated user with cap_net_raw+eip

[Install]
WantedBy=multi-user.target
```

The server can be deployed as a similar service, or via Docker behind nginx.

---

## Data Flow Summary

```
[Classroom PC]
  scapy/psutil captures events
       ↓
  monitors/ → events/queue.py
       ↓
  sender/http_sender.py  (every N seconds, batched POST)
       ↓
[Server: POST /events]
  → stores in DB
  → broadcasts via WebSocket
       ↓
[Dashboard browser]
  WebSocket listener → real-time table of alerts
```

---

## Suggested Development Order

1. **`shared/schemas.py`** — define the Event contract first so agent and server stay in sync.
2. **Agent monitors** — start with `interface_monitor.py` (no root needed with psutil), then `dns_monitor.py`, then `port_monitor.py`.
3. **Server + DB** — ingest endpoint and persistence.
4. **WebSocket broadcaster** — real-time dashboard.
5. **Blacklist management** — remote push from server to agents.

This gives you a clean separation of concerns, makes each component independently testable, and scales naturally from a single classroom to multiple rooms by just pointing agents at the same server URL.
