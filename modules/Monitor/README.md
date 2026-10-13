# Monitoring Module

The `Monitoring` package provides live hardware telemetry, disk partition and network share tracking, application daemon health probes, and an interactive operational dashboard accessible at `http://localhost:5000/monitoring`.

---

## 1. Features & Architecture

* **Hardware Telemetry**: Collects live CPU utilization %, core counts, 1m/5m/15m load averages, CPU package temperature, RAM utilization, and swap metrics via `psutil` and native Linux `/sys` and `/proc` interfaces.
* **Top 10 Processes**: Inspects running processes with dynamic sorting by RAM (`sort=ram`) or CPU (`sort=cpu`). Formats memory resident set size (RSS), % RAM, % CPU, username, PID, and executable command line.
* **Storage & Network Shares**: Inspects OS Root (`/`) and mounted NTFS media drives (`/media/NetworkShare/*`), reporting capacity, used/free space, and alert statuses (`Normal`, `Healthy`, `⚠️ High Usage`, `🚨 Near Full`).
* **Services & Application Matrix**: Non-blocking concurrent probes (0.5s timeout) for local services: Immich, Jellyfin, qBittorrent, Gluetun, n8n, PostgreSQL, AIU Platform, BackendServer, Nginx, Samba, and Tailscale.
* **Diagnostic Test Suite**: Itemized audit across storage alert thresholds, RAM overhead, CPU thermal zone, services availability, and cron log freshness.
* **Responsive Dashboard UI**: Styled after Swagger UI with a clean off-white palette (`#fafafa` canvas, `#ffffff` cards, `#eaeaea` borders, `#1a73e8` blue accents), real-time auto-refresh (Off, 5s, 10s, 30s), interactive process sort switcher, and diagnostic modal.

---

## 2. Endpoints Reference

All endpoints are protected by the global HTTP Basic Authentication middleware configured in `index/index.py`.

### Web Dashboard
* **`GET /monitoring`**
  * **Description**: Renders the complete HTML5/CSS3/Vanilla JS monitoring console.
  * **Response**: `200 OK` (HTML)

### REST Telemetry Endpoints
* **`GET /api/monitoring/system`**
  * **Description**: Returns hardware specifications, CPU load, memory usage, and host details.
  * **Response**:
    ```json
    {
      "hostname": "flash-server",
      "os": "Ubuntu 24.04.2 LTS (Noble Numbat)",
      "kernel": "Linux 6.17.0-20-generic (x86_64)",
      "uptime_formatted": "47d 12h 00m",
      "boot_time": "2026-07-27 11:27:45",
      "lan_ip": "192.168.68.55",
      "tailscale_ip": "100.66.69.41",
      "environment": "Production (flash-server)",
      "cpu": {
        "model": "Intel(R) Core(TM) i5-4590 @ 3.30GHz",
        "cores_physical": 4,
        "cores_logical": 4,
        "load_percent": 14.8,
        "load_avg_1m": 0.45,
        "load_avg_5m": 0.38,
        "load_avg_15m": 0.32,
        "temperature_c": 59.0
      },
      "memory": {
        "total_bytes": 17179869184,
        "used_bytes": 5153960755,
        "available_bytes": 12025908428,
        "percent": 30.0,
        "total_formatted": "16.0 GB",
        "used_formatted": "4.8 GB",
        "available_formatted": "11.2 GB",
        "swap_formatted": "0 B"
      }
    }
    ```

* **`GET /api/monitoring/processes`**
  * **Query Parameters**:
    * `sort`: `"ram"` (default) or `"cpu"`.
    * `limit`: Number of processes to return (default: `10`).
  * **Response**:
    ```json
    {
      "sort_by": "ram",
      "limit": 10,
      "total_processes": 142,
      "ram_in_use_formatted": "4.8 GB / 16.0 GB",
      "processes": [
        {
          "pid": 1373,
          "user": "jellyfin",
          "name": "jellyfin",
          "ram_rss_bytes": 5368709120,
          "ram_rss_formatted": "5.0 GB",
          "ram_percent": 31.2,
          "cpu_percent": 3.4,
          "cmdline": "/usr/bin/jellyfin --webdir=/usr/share/jellyfin/web"
        }
      ]
    }
    ```

* **`GET /api/monitoring/storage`**
  * **Description**: Returns storage capacity, used space, free space, and warning status for all configured partitions and mounted network shares.
  * **Response**:
    ```json
    [
      {
        "name": "OS Root",
        "device": "/dev/sda1",
        "mount_point": "/",
        "model": "Seagate ST500DM002 (500GB)",
        "fstype": "ext4",
        "total_formatted": "459 GB",
        "used_formatted": "352 GB",
        "free_formatted": "89 GB",
        "percent": 80.0,
        "status": "Normal",
        "status_class": "badge-normal"
      },
      {
        "name": "Dragon-Ball",
        "device": "/dev/sdb1",
        "mount_point": "/media/NetworkShare/Dragon-Ball",
        "model": "HGST HTS541010A9 (1TB)",
        "fstype": "ntfs-3g",
        "total_formatted": "932 GB",
        "used_formatted": "894 GB",
        "free_formatted": "39 GB",
        "percent": 96.0,
        "status": "🚨 Near Full",
        "status_class": "badge-critical"
      }
    ]
    ```

* **`GET /api/monitoring/services`**
  * **Description**: Probes all 11 monitored services concurrently with a 0.5s timeout.
  * **Response**:
    ```json
    [
      {
        "id": "immich",
        "name": "Immich Photos & Media",
        "type": "Docker",
        "port": 2283,
        "status": "online",
        "status_class": "badge-healthy",
        "latency_ms": 4.2,
        "note": "HTTP 200 OK (4.2ms)",
        "public_url": "https://pics.stepheng753.com"
      }
    ]
    ```

* **`GET /api/monitoring/diagnostics`**
  * **Description**: Executes health audits across disks, RAM, thermals, services, and cron jobs.
  * **Response**:
    ```json
    {
      "audited_at": "11:19:00 PM",
      "overall_status": "⚠️ 2 Warnings Detected",
      "overall_badge_class": "badge-warning",
      "critical_count": 0,
      "warning_count": 2,
      "total_checks": 10,
      "checks": [
        {
          "category": "Storage",
          "target": "Drive [/media/NetworkShare/Dragon-Ball]",
          "status": "CRITICAL",
          "status_class": "badge-critical",
          "message": "Storage is at 96.0% (39 GB free). Immediate cleanup required!"
        }
      ]
    }
    ```

---

## 3. Configuration

All monitoring targets and warning limits are defined in [modules/Monitor/config.py](config.py):

* **`STORAGE_MOUNTS`**: Array of mount paths to check. Adding a new drive is as simple as appending `{ "name": "...", "path": "/path/to/mount", "device": "/dev/sdX" }`.
* **`SERVICES_MATRIX`**: List of monitored services. Supports `http` checks via `check_url`, `tcp` port checks via `port`, and interface checks like `tailscale`.
* **`DISK_WARNING_THRESHOLD`**: Defaults to `90.0%`.
* **`DISK_CRITICAL_THRESHOLD`**: Defaults to `95.0%`.
* **`CPU_TEMP_WARNING`**: Defaults to `80.0°C`.

---

## 4. Dual-Environment Behavior

* **WSL Development**: Gathers real live CPU/RAM metrics from your WSL VM. Services that are not running locally report `⚪ Standby / Offline` without blocking or throwing 500 errors.
* **Production (`flash-server`)**: Discovers physical partitions (`/dev/sda1`, NTFS mounts) and queries active local daemons.

---

## 5. Package Structure

```
modules/Monitor/
├── __init__.py                # Blueprint export (monitoring_bp)
├── config.py                  # Mount targets, service matrix, thresholds, and WSL detector
├── routes.py                  # Flask route handlers (/monitoring and /api/monitoring/*)
├── collectors/                # Non-blocking telemetry collectors & probes
│   ├── __init__.py            # Collector exports
│   ├── system_collector.py    # CPU load, thermal zone, RAM, swap, and disk inspectors
│   ├── process_collector.py   # Process enumeration with RAM/CPU sort
│   └── service_checker.py     # Concurrent multi-threaded socket probes & diagnostics
├── monitoring.html            # Swagger-styled HTML dashboard with dark mode & modals
├── tests/
│   ├── __init__.py            # Test package marker
│   ├── test_monitoring.py     # Smoke tests against the live host
│   └── test_monitor_logic.py  # Mocked collectors, probes, diagnostics verdicts, and routes
└── README.md                  # Package technical reference
```

---

## 6. Automated Testing

Run all unit tests for the Monitoring module:

```bash
# From repository root
.venv/bin/python -m unittest discover -s modules/Monitor/tests -p "test_*.py"
```



Deeper documentation: [docs/Monitor/](../../docs/Monitor/)
