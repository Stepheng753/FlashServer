import os
import platform

STORAGE_MOUNTS = [
    {"name": "OS Root", "path": "/", "device": "/dev/sda1", "model": "Seagate ST500DM002 (500GB)"},
    {"name": "Dragon-Ball", "path": "/media/NetworkShare/Dragon-Ball", "device": "/dev/sdb1", "model": "HGST HTS541010A9 (1TB)"},
    {"name": "Photos", "path": "/media/NetworkShare/Photos", "device": "/dev/sdc1", "model": "WD WD10JPVX Blue (1TB)"},
    {"name": "CapCut-Videos", "path": "/media/NetworkShare/CapCut-Videos", "device": "/dev/sdd1", "model": "Seagate ST1000LM035 (1TB)"},
    {"name": "TV-Series", "path": "/media/NetworkShare/TV-Series", "device": "/dev/sde2", "model": "WD WD10SPZX Blue (1TB)"},
]

DISK_WARNING_THRESHOLD = 90.0   # Percentage
DISK_CRITICAL_THRESHOLD = 95.0  # Percentage
CPU_TEMP_WARNING = 80.0         # Celsius
RAM_WARNING_THRESHOLD = 90.0    # Percentage

SERVICES_MATRIX = [
    {
        "id": "immich",
        "name": "Immich Photos & Media",
        "type": "Docker",
        "port": 2283,
        "check_url": "http://127.0.0.1:2283/api/server/ping",
        "public_url": "https://pics.stepheng753.com",
        "description": "Immich mobile photo & video auto-backup server"
    },
    {
        "id": "jellyfin",
        "name": "Jellyfin Media Server",
        "type": "Systemd",
        "port": 8096,
        "check_url": "http://127.0.0.1:8096/System/Info/Public",
        "public_url": "https://vids.stepheng753.com",
        "description": "Hardware-accelerated movie & TV streaming server"
    },
    {
        "id": "qbittorrent",
        "name": "qBittorrent Client",
        "type": "Docker (Gluetun)",
        "port": 9090,
        "check_url": "http://127.0.0.1:9090",
        "public_url": "http://192.168.68.55:9090",
        "description": "Torrent download client routed via VPN container"
    },
    {
        "id": "gluetun",
        "name": "Gluetun VPN Tunnel",
        "type": "Docker",
        "port": 8000,
        "check_url": "http://127.0.0.1:8000/v1/openvpn/status",
        "public_url": "http://127.0.0.1:8000",
        "description": "Surfshark OpenVPN network bridge for P2P security"
    },
    {
        "id": "n8n",
        "name": "n8n Workflow Engine",
        "type": "Docker",
        "port": 5678,
        "check_url": "http://127.0.0.1:5678/healthz",
        "public_url": "https://n8n.stepheng753.com",
        "description": "Visual automated webhook & integration pipeline"
    },
    {
        "id": "postgres",
        "name": "PostgreSQL 16 DB",
        "type": "Docker",
        "port": 5432,
        "check_type": "tcp",
        "public_url": "localhost:5432",
        "description": "Primary relational database instance (flash-server DB)"
    },
    {
        "id": "aiu",
        "name": "AIU Voice & Chat Platform",
        "type": "PM2 (Node.js)",
        "port": 3000,
        "check_url": "http://127.0.0.1:3000",
        "public_url": "https://AIU.stepheng753.com",
        "description": "Real-time voice and chat platform backend"
    },
    {
        "id": "backend",
        "name": "BackendServer & Calculator",
        "type": "Gunicorn / Systemd",
        "port": 5000,
        "check_url": "http://127.0.0.1:5000/test",
        "public_url": "https://dev.stepheng753.com",
        "description": "Tutoring billing API, Google Sheets sync, & Twilio dispatcher"
    },
    {
        "id": "nginx",
        "name": "Nginx Reverse Proxy",
        "type": "Systemd",
        "port": 80,
        "check_type": "tcp",
        "public_url": "https://dev.stepheng753.com",
        "description": "Edge HTTPS reverse proxy & SSL termination engine"
    },
    {
        "id": "samba",
        "name": "Samba Network Share",
        "type": "Systemd",
        "port": 445,
        "check_type": "tcp",
        "public_url": "smb://192.168.68.55/NetworkShare",
        "description": "LAN Windows file sharing for /media/NetworkShare"
    },
    {
        "id": "tailscale",
        "name": "Tailscale Mesh VPN",
        "type": "Systemd",
        "port": None,
        "check_type": "tailscale",
        "ip": "100.66.69.41",
        "description": "Encrypted peer-to-peer overlay network"
    }
]

CRON_LOGS = [
    {
        "name": "Weekly Pay Calculator",
        "schedule": "Every Monday at 04:00 AM",
        "path": "/home/flash-server/.logs/cron_calc.log"
    },
    {
        "name": "Weekly SMS Dispatch",
        "schedule": "Every Monday at 12:00 PM UTC",
        "path": "/home/flash-server/.logs/cron_texts.log"
    },
    {
        "name": "Finance Daily Sync",
        "schedule": "Every night at 11:50 PM",
        "path": "/home/flash-server/.logs/cron_finance_sync.log"
    },
    {
        "name": "Recurring Invoices",
        "schedule": "Daily at 05:00 AM",
        "path": "/home/flash-server/.logs/cron_invoices.log"
    }
]

# Detection helper
def is_wsl_environment() -> bool:
    """Returns True if running inside a Windows Subsystem for Linux instance."""
    try:
        if os.path.exists("/proc/version"):
            with open("/proc/version", "r") as f:
                content = f.read().lower()
                if "microsoft" in content or "wsl" in content:
                    return True
    except Exception:
        pass
    return "WSL_DISTRO_NAME" in os.environ or "WSL_INTEROP" in os.environ
