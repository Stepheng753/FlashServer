# Monitoring Telemetry Architecture & Mechanics

This document provides deep technical specifications for the non-blocking hardware collection, memory metrics, and process iteration engines in the `Monitor` module.

---

## 1. Non-Blocking Collection Philosophy

A core requirement for the monitoring engine is that **collecting telemetry must never stall or hang the server**, regardless of whether it is running on a multi-core bare-metal Linux server or inside a Windows Subsystem for Linux (WSL) virtual machine:

1. **Non-Blocking CPU Metrics**:
   - Standard `psutil.cpu_percent(interval=1.0)` blocks the calling thread for 1 full second.
   - The monitoring engine uses `psutil.cpu_percent(interval=None)`, which compares kernel CPU counters immediately against the previous tick with **0.00003s execution time**.
2. **Safe Storage Discovery**:
   - `psutil.disk_partitions(all=False)` can block indefinitely on WSL due to Windows 9p mounts (`/mnt/c`, `/mnt/wsl`).
   - The engine explicitly tests only configured filesystem paths via `os.path.exists()` and `os.statvfs()`, executing in under **0.00001s**.
3. **Concurrent Probes with Strict Timeouts**:
   - Service health checks are dispatched in a `ThreadPoolExecutor` with a strict **0.5s timeout**.

---

## 2. Hardware Telemetry Collectors

Implementation: [modules/Monitor/collectors/system_collector.py](../../modules/Monitor/collectors/system_collector.py)

### 2.1. CPU & Thermal Profile
* **Core Count**:
  * Physical cores: `psutil.cpu_count(logical=False)`
  * Logical cores: `psutil.cpu_count(logical=True)`
* **System Load Averages**:
  * Extracted via `os.getloadavg()`, returning 1-minute, 5-minute, and 15-minute averages.
* **CPU Model Name**:
  * Parsed directly from `/proc/cpuinfo` under `"model name"`, with fallback to `platform.processor()`.
* **Thermal Sensor**:
  * Inspects `psutil.sensors_temperatures()`.
  * Fallback iterates Linux sysfs thermal zones: `/sys/class/thermal/thermal_zone{0,1,2,3}/temp`.
  * Millidegree integers (e.g. `59000`) are converted to Celsius (`59.0°C`).

### 2.2. Memory & Swap Inspection
* **RAM Footprint**:
  * Total, used, free, and available bytes retrieved from `psutil.virtual_memory()`.
  * Formatted into human-readable strings via `format_bytes()` (e.g. `4.8 GB / 16.0 GB`).
* **Swap Utilization**:
  * Queried via `psutil.swap_memory()`.

### 2.3. Host & Network Specs
* **Operating System & Kernel**:
  * Distribution name and release parsed from `/etc/os-release` (e.g. `Ubuntu 24.04.2 LTS`).
  * Kernel version retrieved via `platform.system()`, `platform.release()`, and `platform.machine()`.
* **System Uptime**:
  * Boot timestamp read from `psutil.boot_time()`, formatted into days, hours, and minutes.
* **Network IPs**:
  * Primary LAN IP: Detected via a non-blocking UDP socket connect to `8.8.8.8:80` (without transmitting packets).
  * Tailscale IP: Parsed from `psutil.net_if_addrs()` by locating interface `tailscale0`.

---

## 3. Live Process Iteration & Sorting

Implementation: [modules/Monitor/collectors/process_collector.py](../../modules/Monitor/collectors/process_collector.py)

* **Process Enumeration**:
  * Uses `psutil.process_iter(['pid', 'name', 'username', 'memory_info', 'memory_percent', 'cpu_percent', 'cmdline'])`.
  * Exception handling guards against `psutil.NoSuchProcess`, `psutil.AccessDenied`, and `psutil.ZombieProcess`.
* **Dynamic Sorting**:
  * `sort=ram`: Sorted descending by `ram_rss_bytes`, secondary by `cpu_percent`.
  * `sort=cpu`: Sorted descending by `cpu_percent`, secondary by `ram_rss_bytes`.
* **RSS Calculation**:
  * Resident Set Size (`rss`) measures the exact portion of RAM occupied by the process in memory (excluding swapped-out data).
