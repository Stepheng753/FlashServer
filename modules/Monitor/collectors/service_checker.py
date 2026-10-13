import os
import time
import socket
import datetime
from concurrent.futures import ThreadPoolExecutor
import urllib.request
import urllib.error

from ..config import (
    SERVICES_MATRIX,
    CRON_LOGS,
    DISK_WARNING_THRESHOLD,
    DISK_CRITICAL_THRESHOLD,
    CPU_TEMP_WARNING,
    RAM_WARNING_THRESHOLD,
    is_wsl_environment
)
from .system_collector import get_storage_info, get_cpu_info, get_memory_info


def check_single_service(svc: dict) -> dict:
    """Probes a single service via HTTP or TCP socket with a tight timeout."""
    svc_id = svc["id"]
    name = svc["name"]
    svc_type = svc["type"]
    port = svc.get("port")
    public_url = svc.get("public_url")
    description = svc.get("description")

    start_t = time.perf_counter()
    status = "offline"
    status_class = "badge-offline"
    latency_ms = None
    note = "Unreachable"

    check_url = svc.get("check_url")
    check_type = svc.get("check_type", "http")

    if check_url and check_type == "http":
        try:
            req = urllib.request.Request(check_url, headers={'User-Agent': 'FlashServer-Monitor/1.0'})
            with urllib.request.urlopen(req, timeout=0.5) as response:
                latency_ms = round((time.perf_counter() - start_t) * 1000, 1)
                code = response.getcode()
                if code < 400:
                    status = "online"
                    status_class = "badge-healthy"
                    note = f"HTTP {code} OK ({latency_ms}ms)"
        except urllib.error.HTTPError as e:
            # 401 Unauthorized or 403 Forbidden still proves the service daemon is active!
            latency_ms = round((time.perf_counter() - start_t) * 1000, 1)
            status = "online"
            status_class = "badge-healthy"
            note = f"HTTP {e.code} Active ({latency_ms}ms)"
        except Exception as e:
            status = "offline"
            status_class = "badge-offline"
            note = "Connection Refused / Standby"

    elif check_type == "tcp" and port:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.5)
            res = s.connect_ex(('127.0.0.1', port))
            s.close()
            latency_ms = round((time.perf_counter() - start_t) * 1000, 1)
            if res == 0:
                status = "online"
                status_class = "badge-healthy"
                note = f"Port {port} Open ({latency_ms}ms)"
            else:
                status = "offline"
                status_class = "badge-offline"
                note = f"Port {port} Closed"
        except Exception:
            status = "offline"
            status_class = "badge-offline"
            note = f"Port {port} Closed"

    elif check_type == "tailscale":
        # Check Tailscale interface or socket
        tailscale_active = False
        try:
            import psutil
            addrs = psutil.net_if_addrs()
            for iface in addrs:
                if "tailscale" in iface.lower():
                    tailscale_active = True
                    break
        except Exception:
            pass

        if tailscale_active:
            status = "online"
            status_class = "badge-healthy"
            note = "tailscale0 active"
        else:
            status = "offline"
            status_class = "badge-offline"
            note = "Mesh daemon standby"

    return {
        "id": svc_id,
        "name": name,
        "type": svc_type,
        "port": port,
        "status": status,
        "status_class": status_class,
        "latency_ms": latency_ms,
        "note": note,
        "public_url": public_url,
        "description": description
    }


def get_services_status() -> list:
    """Check all monitored services in parallel."""
    results = []
    with ThreadPoolExecutor(max_workers=len(SERVICES_MATRIX)) as executor:
        futures = [executor.submit(check_single_service, svc) for svc in SERVICES_MATRIX]
        for f in futures:
            results.append(f.result())

    return results


def run_diagnostics() -> dict:
    """
    Executes a complete diagnostic test suite across hardware, disks,
    critical services, and background cron schedules.
    """
    audit_time = datetime.datetime.now().strftime("%I:%M:%S %p")
    checks = []
    critical_count = 0
    warning_count = 0

    # 1. Storage Audits
    storage_list = get_storage_info()

    for disk in storage_list:
        pct = disk.get("percent", 0)
        mount = disk.get("mount_point", disk.get("name"))
        if pct >= DISK_CRITICAL_THRESHOLD:
            critical_count += 1
            checks.append({
                "category": "Storage",
                "target": f"Drive [{mount}]",
                "status": "CRITICAL",
                "status_class": "badge-critical",
                "message": f"Storage is at {pct}% ({disk.get('free_formatted', 'low')} free). Immediate cleanup required!"
            })
        elif pct >= DISK_WARNING_THRESHOLD:
            warning_count += 1
            checks.append({
                "category": "Storage",
                "target": f"Drive [{mount}]",
                "status": "WARNING",
                "status_class": "badge-warning",
                "message": f"Storage is at {pct}% ({disk.get('free_formatted', 'low')} free). Nearing capacity."
            })
        else:
            checks.append({
                "category": "Storage",
                "target": f"Drive [{mount}]",
                "status": "PASS",
                "status_class": "badge-healthy",
                "message": f"Healthy utilization ({pct}% used, {disk.get('free_formatted', 'ample')} free)."
            })

    # 2. Memory Audit
    mem_info = get_memory_info()
    mem_pct = mem_info.get("percent", 0)
    mem_avail = mem_info.get("available_formatted", "N/A")

    if mem_pct >= RAM_WARNING_THRESHOLD:
        warning_count += 1
        checks.append({
            "category": "Memory",
            "target": "System RAM",
            "status": "WARNING",
            "status_class": "badge-warning",
            "message": f"High memory consumption: {mem_pct}% used ({mem_avail} available)."
        })
    else:
        checks.append({
            "category": "Memory",
            "target": "System RAM",
            "status": "PASS",
            "status_class": "badge-healthy",
            "message": f"RAM overhead nominal: {mem_pct}% used ({mem_avail} available)."
        })

    # 3. CPU Temperature & Load Audit
    cpu_info = get_cpu_info()
    cpu_temp = cpu_info.get("temperature_c")
    cpu_load = cpu_info.get("load_percent", 0)

    if cpu_temp and cpu_temp >= CPU_TEMP_WARNING:
        warning_count += 1
        checks.append({
            "category": "CPU Thermal",
            "target": "Intel Package Thermal Zone",
            "status": "WARNING",
            "status_class": "badge-warning",
            "message": f"Elevated package temp: {cpu_temp}°C (Load: {cpu_load}%)."
        })
    else:
        temp_disp = f"{cpu_temp}°C" if cpu_temp else "Normal"
        checks.append({
            "category": "CPU Thermal",
            "target": "CPU Package",
            "status": "PASS",
            "status_class": "badge-healthy",
            "message": f"Thermal profile normal ({temp_disp}, Load: {cpu_load}%)."
        })

    # 4. Service Daemons Audit
    services = get_services_status()
    online_count = sum(1 for s in services if s["status"] == "online")
    total_services = len(services)
    if is_wsl_environment():
        checks.append({
            "category": "Services Matrix",
            "target": "Local WSL Daemons",
            "status": "INFO",
            "status_class": "badge-normal",
            "message": f"{online_count}/{total_services} services online locally. (WSL development standby)."
        })
    else:
        if online_count == total_services:
            checks.append({
                "category": "Services Matrix",
                "target": "Core Services (Immich, Jellyfin, etc.)",
                "status": "PASS",
                "status_class": "badge-healthy",
                "message": f"All {total_services} production daemons responding normally."
            })
        else:
            offline_names = [s["name"] for s in services if s["status"] != "online"]
            warning_count += 1
            checks.append({
                "category": "Services Matrix",
                "target": "Daemon Availability",
                "status": "WARNING",
                "status_class": "badge-warning",
                "message": f"{len(offline_names)} services offline: {', '.join(offline_names[:3])}."
            })

    # 5. Cron Job Logs Freshness
    for cron in CRON_LOGS:
        cron_path = cron["path"]
        if os.path.exists(cron_path):
            mtime = os.path.getmtime(cron_path)
            last_dt = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
            checks.append({
                "category": "Automation",
                "target": cron["name"],
                "status": "PASS",
                "status_class": "badge-healthy",
                "message": f"Cron log verified. Last updated: {last_dt}."
            })
        else:
            checks.append({
                "category": "Automation",
                "target": cron["name"],
                "status": "INFO",
                "status_class": "badge-normal",
                "message": f"Scheduled for {cron['schedule']} (Standby in WSL / uncreated)."
            })

    # Overall Summary
    if critical_count > 0:
        overall_status = f"{critical_count} Critical Storage Alert{'s' if critical_count > 1 else ''}"
        overall_badge_class = "badge-critical"
    elif warning_count > 0:
        overall_status = f"{warning_count} Warning{'s' if warning_count > 1 else ''} Detected"
        overall_badge_class = "badge-warning"
    else:
        overall_status = "All Systems Nominal"
        overall_badge_class = "badge-nominal"

    return {
        "audited_at": audit_time,
        "overall_status": overall_status,
        "overall_badge_class": overall_badge_class,
        "critical_count": critical_count,
        "warning_count": warning_count,
        "total_checks": len(checks),
        "checks": checks
    }
