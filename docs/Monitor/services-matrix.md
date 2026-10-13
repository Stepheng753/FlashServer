# Services Matrix & Health Probes Guide

This document details the configuration, network targets, and health evaluation mechanics for all monitored services running on `flash-server`.

---

## 1. Monitored Services Reference

Configuration file: [modules/Monitor/config.py](../../modules/Monitor/config.py)

| Service ID | Service Name | Runtime | Port / Target | Probe Type | Public URL | Description |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`immich`** | Immich Photos | Docker | `2283` | HTTP `/api/server/ping` | `https://pics.stepheng753.com` | Automated mobile photo & video backup |
| **`jellyfin`** | Jellyfin Server | Systemd | `8096` | HTTP `/System/Info/Public` | `https://vids.stepheng753.com` | Movie & TV streaming server |
| **`qbittorrent`** | qBittorrent Web UI | Docker (Gluetun) | `9090` | HTTP `http://127.0.0.1:9090` | `http://192.168.68.55:9090` | Torrent downloader via VPN network stack |
| **`gluetun`** | Gluetun VPN Tunnel | Docker | `8000` | HTTP `/v1/openvpn/status` | `http://127.0.0.1:8000` | Surfshark OpenVPN container bridge |
| **`n8n`** | n8n Automation | Docker | `5678` | HTTP `/healthz` | `https://n8n.stepheng753.com` | Workflow automation and webhooks |
| **`postgres`** | PostgreSQL 16 DB | Docker | `5432` | TCP Socket | `localhost:5432` | Primary database instance |
| **`aiu`** | AIU Platform | PM2 (Node.js) | `3000` | HTTP `http://127.0.0.1:3000` | `https://AIU.stepheng753.com` | Voice and chat platform backend |
| **`backend`** | BackendServer | Systemd / Flask | `5000` | HTTP `/test` | `https://dev.stepheng753.com` | Tutoring billing and monitoring backend |
| **`nginx`** | Nginx Reverse Proxy | Systemd | `80` | TCP Socket | `https://dev.stepheng753.com` | Edge reverse proxy & SSL termination |
| **`samba`** | Samba Windows Share | Systemd | `445` | TCP Socket | `smb://192.168.68.55/NetworkShare` | LAN file sharing for `/media/NetworkShare` |
| **`tailscale`** | Tailscale Mesh VPN | Systemd | N/A | Interface (`tailscale0`) | `100.66.69.41` | Encrypted peer-to-peer overlay network |

---

## 2. Health Probe Mechanics

Implementation: [modules/Monitor/collectors/service_checker.py](../../modules/Monitor/collectors/service_checker.py)

### 2.1. HTTP Probes
* Probes send a lightweight HTTP `GET` request with a user-agent header.
* Responses returning status codes `< 400` are marked as `🟢 Online`.
* Responses returning `401 Unauthorized` or `403 Forbidden` (such as protected dashboards) are also marked as `🟢 Online` because the daemon is responsive and functioning properly.
* Latency is measured in milliseconds using `time.perf_counter()`.

### 2.2. TCP Socket Probes
* For non-HTTP daemons (like PostgreSQL or Samba), a TCP socket connection is opened to `127.0.0.1:<port>` with `s.settimeout(0.5)`.
* If the port accepts the connection (`connect_ex == 0`), the service is marked as `🟢 Online`.

---

## 3. How to Add a New Service

To monitor a new service or container on `flash-server`:

1. Open [modules/Monitor/config.py](../../modules/Monitor/config.py).
2. Append a new dictionary to the `SERVICES_MATRIX` list:
   ```python
   {
       "id": "redis",
       "name": "Redis Cache",
       "type": "Docker",
       "port": 6379,
       "check_type": "tcp",
       "public_url": "localhost:6379",
       "description": "In-memory caching and session store"
   }
   ```
3. Save the file. The new service will immediately appear on the dashboard with real-time status and latency.

---

## 4. Alert Thresholds Configuration

The diagnostic suite evaluates the following thresholds defined in [modules/Monitor/config.py](../../modules/Monitor/config.py):

```python
DISK_WARNING_THRESHOLD = 90.0   # Storage capacity warning limit (amber badge)
DISK_CRITICAL_THRESHOLD = 95.0  # Storage critical limit (red alert badge)
CPU_TEMP_WARNING = 80.0         # CPU thermal zone warning threshold (°C)
RAM_WARNING_THRESHOLD = 90.0    # Memory consumption warning threshold (%)
```
