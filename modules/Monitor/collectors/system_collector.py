import os
import time
import socket
import platform
import datetime
import psutil
from ..config import (
    STORAGE_MOUNTS,
    DISK_WARNING_THRESHOLD,
    DISK_CRITICAL_THRESHOLD,
    is_wsl_environment
)


def format_bytes(byte_count: float) -> str:
    """Format bytes into readable string (e.g., 4.8 GB, 89 MB)."""
    if byte_count is None:
        return "N/A"
    power = 1024
    n = 0
    power_labels = {0: 'B', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB', 5: 'PB'}
    while byte_count >= power and n < 5:
        byte_count /= power
        n += 1
    return f"{byte_count:.1f} {power_labels[n]}"


def get_cpu_info() -> dict:
    """Get live CPU telemetry including load %, cores, load average, and temperature."""
    try:
        load_pct = round(psutil.cpu_percent(interval=None), 1)
    except Exception:
        load_pct = 0.0

    logical_cores = psutil.cpu_count(logical=True) or 1
    physical_cores = psutil.cpu_count(logical=False) or logical_cores

    # Load average (1m, 5m, 15m)
    try:
        load_avg = os.getloadavg()
    except Exception:
        load_avg = (0.0, 0.0, 0.0)

    # CPU Model Name
    model_name = "Generic x86_64 Processor"
    try:
        if os.path.exists("/proc/cpuinfo"):
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if "model name" in line:
                        model_name = line.split(":", 1)[1].strip()
                        break
        else:
            model_name = platform.processor() or platform.machine()
    except Exception:
        model_name = platform.processor() or "Intel Core Processor"

    # CPU Temperature
    temp_c = None
    try:
        # Check psutil sensors
        if hasattr(psutil, "sensors_temperatures"):
            temps = psutil.sensors_temperatures()
            if temps:
                for name, entries in temps.items():
                    if entries:
                        temp_c = round(entries[0].current, 1)
                        break
        # Fallback to sysfs thermal zones (e.g., thermal_zone2 on flash-server)
        if temp_c is None:
            for zone_idx in [2, 0, 1, 3]:
                path = f"/sys/class/thermal/thermal_zone{zone_idx}/temp"
                if os.path.exists(path):
                    with open(path, "r") as f:
                        raw = float(f.read().strip())
                        temp_c = round(raw / 1000.0, 1)
                        break
    except Exception:
        temp_c = None

    return {
        "model": model_name,
        "cores_physical": physical_cores,
        "cores_logical": logical_cores,
        "load_percent": load_pct,
        "load_avg_1m": round(load_avg[0], 2),
        "load_avg_5m": round(load_avg[1], 2),
        "load_avg_15m": round(load_avg[2], 2),
        "temperature_c": temp_c
    }


def get_memory_info() -> dict:
    """Get live RAM and Swap usage."""
    try:
        vm = psutil.virtual_memory()
        swap = psutil.swap_memory()
        return {
            "total_bytes": vm.total,
            "used_bytes": vm.used,
            "free_bytes": vm.free,
            "available_bytes": vm.available,
            "percent": round(vm.percent, 1),
            "total_formatted": format_bytes(vm.total),
            "used_formatted": format_bytes(vm.used),
            "available_formatted": format_bytes(vm.available),
            "swap_total_bytes": swap.total,
            "swap_used_bytes": swap.used,
            "swap_percent": round(swap.percent, 1),
            "swap_formatted": format_bytes(swap.used)
        }
    except Exception as e:
        return {
            "total_bytes": 0, "used_bytes": 0, "free_bytes": 0, "available_bytes": 0,
            "percent": 0.0, "total_formatted": "N/A", "used_formatted": "N/A",
            "available_formatted": "N/A", "swap_total_bytes": 0, "swap_used_bytes": 0,
            "swap_percent": 0.0, "swap_formatted": "0 B", "error": str(e)
        }


def get_storage_info() -> list:
    """
    Inspects mounted storage drives and flash-server network shares.
    Safely computes usage without hanging on disconnected drives.
    """
    results = []
    seen_mounts = set()

    # 1. Process configured target mounts
    for entry in STORAGE_MOUNTS:
        mount_path = entry["path"]
        seen_mounts.add(mount_path)
        item = {
            "name": entry["name"],
            "device": entry["device"],
            "mount_point": mount_path,
            "model": entry.get("model", "Storage Device"),
            "fstype": "ext4" if mount_path == "/" else "ntfs-3g"
        }

        if os.path.exists(mount_path):
            try:
                usage = psutil.disk_usage(mount_path)
                item["total_bytes"] = usage.total
                item["used_bytes"] = usage.used
                item["free_bytes"] = usage.free
                item["percent"] = round(usage.percent, 1)
                item["total_formatted"] = format_bytes(usage.total)
                item["used_formatted"] = format_bytes(usage.used)
                item["free_formatted"] = format_bytes(usage.free)

                if item["percent"] >= DISK_CRITICAL_THRESHOLD:
                    item["status"] = "Near Full"
                    item["status_class"] = "badge-critical"
                elif item["percent"] >= DISK_WARNING_THRESHOLD:
                    item["status"] = "High Usage"
                    item["status_class"] = "badge-warning"
                else:
                    item["status"] = "Healthy"
                    item["status_class"] = "badge-healthy"
            except Exception:
                item["status"] = "Mounted (Unreadable)"
                item["status_class"] = "badge-warning"
                item["percent"] = 0
                item["total_formatted"] = "N/A"
                item["used_formatted"] = "N/A"
                item["free_formatted"] = "N/A"
        else:
            # Mount point doesn't exist on this host (e.g., local WSL dev)
            item["status"] = "Configured (Prod Target)"
            item["status_class"] = "badge-normal"
            item["percent"] = 0
            item["total_formatted"] = "Offline in WSL"
            item["used_formatted"] = "0 B"
            item["free_formatted"] = "N/A"

        results.append(item)

    # 2. Check /home partition if it exists and is distinct from /
    if os.path.exists("/home") and "/home" not in seen_mounts:
        try:
            # Only add if it has a different device id from /
            if os.stat("/home").st_dev != os.stat("/").st_dev:
                usage = psutil.disk_usage("/home")
                pct = round(usage.percent, 1)
                results.append({
                    "name": "Home Storage",
                    "device": "/dev/home",
                    "mount_point": "/home",
                    "model": "User Partition",
                    "fstype": "ext4",
                    "total_bytes": usage.total,
                    "used_bytes": usage.used,
                    "free_bytes": usage.free,
                    "percent": pct,
                    "total_formatted": format_bytes(usage.total),
                    "used_formatted": format_bytes(usage.used),
                    "free_formatted": format_bytes(usage.free),
                    "status": "Healthy" if pct < DISK_WARNING_THRESHOLD else ("High Usage" if pct < DISK_CRITICAL_THRESHOLD else "Near Full"),
                    "status_class": "badge-healthy" if pct < DISK_WARNING_THRESHOLD else ("badge-warning" if pct < DISK_CRITICAL_THRESHOLD else "badge-critical")
                })
        except Exception:
            pass

    return results


def get_uptime_info() -> tuple[float, str, str]:
    """Get system uptime in seconds, formatted string, and boot datetime."""
    try:
        boot_time_ts = psutil.boot_time()
        uptime_seconds = time.time() - boot_time_ts
        boot_datetime = datetime.datetime.fromtimestamp(boot_time_ts).strftime("%Y-%m-%d %H:%M:%S")

        days = int(uptime_seconds // (24 * 3600))
        rem = uptime_seconds % (24 * 3600)
        hours = int(rem // 3600)
        minutes = int((rem % 3600) // 60)

        if days > 0:
            formatted = f"{days}d {hours}h {minutes}m"
        else:
            formatted = f"{hours}h {minutes}m"

        return uptime_seconds, formatted, boot_datetime
    except Exception:
        return 0, "0m", "Unknown"


def get_network_ips() -> tuple[str, str]:
    """Find local Primary LAN IP and Tailscale IP."""
    lan_ip = "127.0.0.1"
    tailscale_ip = "100.66.69.41 (Not Bound)"

    # Detect LAN IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.1)
        s.connect(("8.8.8.8", 80))
        lan_ip = s.getsockname()[0]
        s.close()
    except Exception:
        lan_ip = "127.0.0.1"

    # Detect Tailscale IP if tailscale0 is up
    try:
        addrs = psutil.net_if_addrs()
        for iface_name, iface_addrs in addrs.items():
            if "tailscale" in iface_name.lower():
                for addr in iface_addrs:
                    if addr.family == socket.AF_INET:
                        tailscale_ip = addr.address
                        break
    except Exception:
        pass

    return lan_ip, tailscale_ip


def get_os_info() -> str:
    """Parse pretty OS name from /etc/os-release or platform."""
    try:
        if os.path.exists("/etc/os-release"):
            with open("/etc/os-release") as f:
                data = {}
                for line in f:
                    if "=" in line:
                        k, v = line.strip().split("=", 1)
                        data[k] = v.strip('"')
                return data.get("PRETTY_NAME", "Ubuntu Linux")
    except Exception:
        pass
    return f"{platform.system()} {platform.release()}"


def collect_system_telemetry() -> dict:
    """Assembles full live system overview and telemetry."""
    uptime_sec, uptime_str, boot_dt = get_uptime_info()
    lan_ip, ts_ip = get_network_ips()
    is_wsl = is_wsl_environment()

    return {
        "hostname": platform.node(),
        "os": get_os_info(),
        "kernel": f"{platform.system()} {platform.release()} ({platform.machine()})",
        "uptime_seconds": uptime_sec,
        "uptime_formatted": uptime_str,
        "boot_time": boot_dt,
        "lan_ip": lan_ip,
        "tailscale_ip": ts_ip,
        "environment": "WSL (Development)" if is_wsl else "Production (flash-server)",
        "is_wsl": is_wsl,
        "cpu": get_cpu_info(),
        "memory": get_memory_info()
    }
