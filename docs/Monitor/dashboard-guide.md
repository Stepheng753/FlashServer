# Monitoring Dashboard User Guide

This guide describes the user interface, interaction model, and diagnostic features of the **System Health & Operational Telemetry Dashboard** served at `http://localhost:5000/monitoring`.

---

## 1. Visual Hierarchy & Components

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Flash Server Monitoring                       [📖 Swagger Docs]            │
├─────────────────────────────────────────────────────────────────────────────┤
│  [♥] System Health & Operational Telemetry  ● All Systems Nominal           │
│      Live hardware telemetry, daemon process matrix, disk audits...         │
│      Audited: 11:19:00 PM    [Auto-refresh: 10s ▼] [▷ Run Diagnostics] [🔄] │
├─────────────────────────────────────────────────────────────────────────────┤
│  ⚙ HARDWARE & OPERATING SYSTEM                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │ CPU LOAD     │  │ MEMORY (RAM) │  │ STORAGE (OS) │  │ HOST & KERNEL  │  │
│  │ 14.8% [====] │  │ 30.0% [====] │  │ 80.0% [====] │  │ [Ubuntu]       │  │
│  │ 4C / 4T      │  │ 4.8G / 16.0G │  │ 352G / 459G  │  │ flash-server   │  │
│  │ Load: 0.45   │  │ Free: 11.2GB │  │ Free: 89 GB  │  │ Linux 6.17.0   │  │
│  │ Temp: 59.0°C │  │ Swap: 0 B    │  │ Normal       │  │ Up: 47d 12h    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └────────────────┘  │
├─────────────────────────────────────────────────────────────────────────────┤
│  TOP 10 PROCESSES                    [Sort by RAM] [Sort by CPU]            │
│  #  PID   USER    PROCESS   RAM(RSS)  % MEMORY    % CPU    COMMAND          │
│  1  1373  jelly   jellyfin  5.0 GB    31.2% [==]  3.4% [=] /usr/bin/...    │
├─────────────────────────────────────────────────────────────────────────────┤
│  STORAGE DEVICES & MOUNTS (/etc/fstab)                                      │
│  DEVICE     MOUNT                  CAPACITY   USED    FREE    USE %  STATUS │
│  /dev/sda1  /                      459 GB     352 GB  89 GB   80%    Normal │
│  /dev/sdb1  /media/.../Dragon-Ball 932 GB     894 GB  39 GB   96%   🚨 Near │
├─────────────────────────────────────────────────────────────────────────────┤
│  SERVICES & APPLICATION MATRIX                                              │
│  ┌──────────────────────┐  ┌──────────────────────┐  ┌───────────────────┐  │
│  │ Immich Photos 🟢     │  │ Jellyfin Media 🟢    │  │ qBittorrent 🟢   │  │
│  │ Docker · 4.2ms       │  │ Systemd · 2.1ms      │  │ Docker · 1.8ms    │  │
│  │ Port :2283  Launch ↗ │  │ Port :8096  Launch ↗ │  │ Port :9090  ↗     │  │
│  └──────────────────────┘  └──────────────────────┘  └───────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Interactive Features

### 2.1. Auto-Refresh Intervals
Located in the header controls:
* Options: **Off**, **5 seconds**, **10 seconds** (default), and **30 seconds**.
* When enabled, a timer asynchronously triggers all telemetry endpoints in parallel without reloading the webpage.
* Click the **[🔄 Refresh All]** button at any time to immediately poll the server.

### 2.2. Process Sorting (RAM vs. CPU)
Toggle between:
* **`Sort by RAM`**: Sorts processes descending by resident memory consumption (`rss`). Useful for identifying memory leaks or heavy daemon footprints.
* **`Sort by CPU`**: Sorts processes descending by active CPU core utilization.

### 2.3. System Diagnostic Audit Suite
Clicking **`▷ Run Diagnostic Suite`** opens an interactive modal:
* Runs health checks across storage mount limits, memory saturation, CPU thermal zones, and service responsiveness.
* Highlights warnings and critical items with clear remediation advice (e.g. storage cleanup recommendations).
* Includes a **Re-run Audit** button inside the modal for immediate re-verification.

---

## 3. Styling & Color Palette

The monitoring dashboard adheres to Swagger UI design aesthetics:
* **Background Canvas**: `#fafafa`
* **Card Surfaces**: `#ffffff` with subtle `1px solid #e8eaed` borders and rounded corners (`12px`).
* **Primary Accents**: Google/Material Blue (`#1a73e8`), with `#1557b0` hover states.
* **Status Badges**:
  * Nominal / Healthy: `#e6f4ea` background with `#137333` text.
  * Warning / High Usage: `#fef7e0` background with `#b06000` text.
  * Critical / Near Full: `#fce8e6` background with `#c5221f` text.
  * Host / Ubuntu: `#fff1e5` background with `#c2410c` text.
