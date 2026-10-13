import os
import socket
import sys
import unittest
import urllib.error
from collections import namedtuple
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import psutil
from flask import Flask

# Add repo root to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from modules.Monitor import config as monitor_config
from modules.Monitor.collectors import service_checker, system_collector
from modules.Monitor.collectors.process_collector import get_top_processes
from modules.Monitor.routes import monitoring_bp

DiskUsage = namedtuple("DiskUsage", "total used free percent")


class TestFormatBytes(unittest.TestCase):

    def test_units_and_edges(self):
        self.assertEqual(system_collector.format_bytes(None), "N/A")
        self.assertEqual(system_collector.format_bytes(1023), "1023.0 B")
        self.assertEqual(system_collector.format_bytes(1024 ** 4), "1.0 TB")
        # Never goes past PB
        self.assertEqual(system_collector.format_bytes(1024 ** 6), "1024.0 PB")


class TestWslDetection(unittest.TestCase):

    def test_detects_wsl_from_proc_version(self):
        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", unittest.mock.mock_open(read_data="Linux version 5.15 microsoft-standard-WSL2")):
            self.assertTrue(monitor_config.is_wsl_environment())

    def test_native_linux_without_env_vars(self):
        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", unittest.mock.mock_open(read_data="Linux version 6.8 generic")), \
             patch.dict(os.environ, {}, clear=True):
            self.assertFalse(monitor_config.is_wsl_environment())

    def test_env_var_fallback_when_proc_unreadable(self):
        with patch("os.path.exists", return_value=False), \
             patch.dict(os.environ, {"WSL_DISTRO_NAME": "Ubuntu"}, clear=True):
            self.assertTrue(monitor_config.is_wsl_environment())


class TestSystemCollectors(unittest.TestCase):

    def test_uptime_formatting(self):
        with patch("psutil.boot_time", return_value=1_000_000), patch("time.time", return_value=1_000_000 + 2 * 86400 + 3 * 3600 + 5 * 60):
            seconds, text, _ = system_collector.get_uptime_info()
        self.assertEqual(text, "2d 3h 5m")
        with patch("psutil.boot_time", return_value=1_000_000), patch("time.time", return_value=1_000_000 + 3600 + 120):
            self.assertEqual(system_collector.get_uptime_info()[1], "1h 2m")

    def test_uptime_failure_returns_defaults(self):
        with patch("psutil.boot_time", side_effect=RuntimeError("boom")):
            self.assertEqual(system_collector.get_uptime_info(), (0, "0m", "Unknown"))

    def test_memory_info_success_and_failure(self):
        vm = SimpleNamespace(total=8 * 1024 ** 3, used=4 * 1024 ** 3, free=2 * 1024 ** 3, available=3 * 1024 ** 3, percent=50.04)
        swap = SimpleNamespace(total=1024 ** 3, used=0, percent=0.0)
        with patch("psutil.virtual_memory", return_value=vm), patch("psutil.swap_memory", return_value=swap):
            mem = system_collector.get_memory_info()
        self.assertEqual(mem["percent"], 50.0)
        self.assertEqual(mem["total_formatted"], "8.0 GB")
        self.assertEqual(mem["swap_formatted"], "0.0 B")

        with patch("psutil.virtual_memory", side_effect=RuntimeError("no mem")):
            mem = system_collector.get_memory_info()
        self.assertEqual(mem["percent"], 0.0)
        self.assertEqual(mem["error"], "no mem")

    def test_cpu_temperature_from_psutil_and_failure(self):
        entry = SimpleNamespace(current=61.234)
        with patch("psutil.sensors_temperatures", return_value={"coretemp": [entry]}, create=True):
            self.assertEqual(system_collector.get_cpu_info()["temperature_c"], 61.2)
        with patch("psutil.sensors_temperatures", side_effect=RuntimeError("x"), create=True):
            self.assertIsNone(system_collector.get_cpu_info()["temperature_c"])

    def test_cpu_load_average_failure_defaults_to_zero(self):
        with patch("os.getloadavg", side_effect=OSError):
            cpu = system_collector.get_cpu_info()
        self.assertEqual((cpu["load_avg_1m"], cpu["load_avg_5m"], cpu["load_avg_15m"]), (0.0, 0.0, 0.0))

    def test_network_ips_finds_tailscale_interface(self):
        addr = SimpleNamespace(family=socket.AF_INET, address="100.64.0.7")
        with patch("psutil.net_if_addrs", return_value={"eth0": [], "tailscale0": [addr]}):
            _, ts_ip = system_collector.get_network_ips()
        self.assertEqual(ts_ip, "100.64.0.7")

    def test_network_ips_without_tailscale_uses_placeholder(self):
        with patch("psutil.net_if_addrs", return_value={"eth0": []}):
            _, ts_ip = system_collector.get_network_ips()
        self.assertIn("Not Bound", ts_ip)

    def test_os_info_reads_pretty_name(self):
        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", unittest.mock.mock_open(read_data='NAME="Ubuntu"\nPRETTY_NAME="Ubuntu 24.04 LTS"\n')):
            self.assertEqual(system_collector.get_os_info(), "Ubuntu 24.04 LTS")

    def test_collect_system_telemetry_environment_label(self):
        with patch.object(system_collector, "is_wsl_environment", return_value=True):
            self.assertEqual(system_collector.collect_system_telemetry()["environment"], "WSL (Development)")
        with patch.object(system_collector, "is_wsl_environment", return_value=False):
            data = system_collector.collect_system_telemetry()
        self.assertEqual(data["environment"], "Production (flash-server)")
        self.assertFalse(data["is_wsl"])


class TestStorageInfo(unittest.TestCase):

    MOUNTS = [
        {"name": "Healthy", "path": "/healthy", "device": "/dev/a"},
        {"name": "High", "path": "/high", "device": "/dev/b"},
        {"name": "Full", "path": "/full", "device": "/dev/c"},
        {"name": "Missing", "path": "/missing", "device": "/dev/d"},
    ]

    def usage(self, path):
        return {"/healthy": DiskUsage(100, 50, 50, 50.0),
                "/high": DiskUsage(100, 92, 8, 92.0),
                "/full": DiskUsage(100, 97, 3, 97.0)}[path]

    def test_status_per_threshold_and_missing_mount(self):
        with patch.object(system_collector, "STORAGE_MOUNTS", self.MOUNTS), \
             patch("os.path.exists", side_effect=lambda p: p != "/missing" and p != "/home"), \
             patch("psutil.disk_usage", side_effect=self.usage):
            result = {d["name"]: d for d in system_collector.get_storage_info()}
        self.assertEqual(result["Healthy"]["status"], "Healthy")
        self.assertEqual(result["High"]["status"], "High Usage")
        self.assertEqual(result["High"]["status_class"], "badge-warning")
        self.assertEqual(result["Full"]["status"], "Near Full")
        self.assertEqual(result["Full"]["status_class"], "badge-critical")
        self.assertEqual(result["Missing"]["status"], "Configured (Prod Target)")
        self.assertEqual(result["Missing"]["percent"], 0)

    def test_unreadable_mount_is_reported_not_raised(self):
        with patch.object(system_collector, "STORAGE_MOUNTS", self.MOUNTS[:1]), \
             patch("os.path.exists", side_effect=lambda p: p != "/home"), \
             patch("psutil.disk_usage", side_effect=PermissionError):
            result = system_collector.get_storage_info()
        self.assertEqual(result[0]["status"], "Mounted (Unreadable)")

    def test_separate_home_partition_is_appended(self):
        stats = {"/home": SimpleNamespace(st_dev=2), "/": SimpleNamespace(st_dev=1)}
        with patch.object(system_collector, "STORAGE_MOUNTS", []), \
             patch("os.path.exists", return_value=True), \
             patch("os.stat", side_effect=lambda p: stats[p]), \
             patch("psutil.disk_usage", return_value=DiskUsage(100, 10, 90, 10.0)):
            result = system_collector.get_storage_info()
        self.assertEqual([d["name"] for d in result], ["Home Storage"])


class TestProcessCollector(unittest.TestCase):

    @staticmethod
    def fake_proc(pid, name, rss, cpu, cmdline=None, username="root", mem_pct=1.0):
        return SimpleNamespace(info={
            "pid": pid, "name": name, "username": username, "memory_info": SimpleNamespace(rss=rss),
            "memory_percent": mem_pct, "cpu_percent": cpu, "cmdline": cmdline,
        })

    def processes(self):
        class Denied:
            @property
            def info(self):
                raise psutil.AccessDenied()
        return [
            self.fake_proc(1, "small", 100, 50.0, ["small", "--flag"]),
            self.fake_proc(2, "big", 5000, 1.0, None, username=None),
            self.fake_proc(3, "mid", 1000, 10.0),
            Denied(),
        ]

    def test_sorts_by_ram_and_ranks(self):
        with patch("psutil.process_iter", return_value=self.processes()):
            result = get_top_processes(sort_by="ram", limit=2)
        self.assertEqual([p["name"] for p in result["processes"]], ["big", "mid"])
        self.assertEqual([p["rank"] for p in result["processes"]], [1, 2])
        self.assertEqual(result["total_processes_count"], 4)
        self.assertEqual(result["total_rss_bytes"], 6100)

    def test_sorts_by_cpu_case_insensitive(self):
        with patch("psutil.process_iter", return_value=self.processes()):
            result = get_top_processes(sort_by="CPU", limit=10)
        self.assertEqual(result["processes"][0]["name"], "small")
        self.assertEqual(len(result["processes"]), 3)  # AccessDenied process skipped

    def test_command_line_and_username_fallbacks(self):
        with patch("psutil.process_iter", return_value=self.processes()):
            procs = {p["name"]: p for p in get_top_processes(limit=10)["processes"]}
        self.assertEqual(procs["small"]["cmdline"], "small --flag")
        self.assertEqual(procs["big"]["cmdline"], "big")
        self.assertEqual(procs["big"]["username"], "system")


class TestServiceChecker(unittest.TestCase):

    def http_service(self):
        return {"id": "web", "name": "Web", "type": "Docker", "port": 80,
                "check_url": "http://127.0.0.1:80/", "check_type": "http", "public_url": "https://x", "description": "d"}

    def test_http_ok_is_online(self):
        response = MagicMock()
        response.getcode.return_value = 200
        response.__enter__.return_value = response
        with patch("urllib.request.urlopen", return_value=response):
            result = service_checker.check_single_service(self.http_service())
        self.assertEqual(result["status"], "online")
        self.assertEqual(result["status_class"], "badge-healthy")
        self.assertIn("HTTP 200", result["note"])

    def test_http_auth_error_still_counts_as_online(self):
        err = urllib.error.HTTPError("http://x", 401, "Unauthorized", {}, None)
        with patch("urllib.request.urlopen", side_effect=err):
            result = service_checker.check_single_service(self.http_service())
        self.assertEqual(result["status"], "online")
        self.assertIn("401", result["note"])

    def test_http_connection_failure_is_offline(self):
        with patch("urllib.request.urlopen", side_effect=ConnectionRefusedError):
            result = service_checker.check_single_service(self.http_service())
        self.assertEqual(result["status"], "offline")
        self.assertEqual(result["status_class"], "badge-offline")
        self.assertIsNone(result["latency_ms"])

    def test_tcp_open_and_closed(self):
        svc = {"id": "db", "name": "DB", "type": "Systemd", "port": 5432, "check_type": "tcp"}
        sock = MagicMock()
        with patch("socket.socket", return_value=sock):
            sock.connect_ex.return_value = 0
            self.assertEqual(service_checker.check_single_service(svc)["status"], "online")
            sock.connect_ex.return_value = 111
            closed = service_checker.check_single_service(svc)
        self.assertEqual(closed["status"], "offline")
        self.assertEqual(closed["note"], "Port 5432 Closed")
        sock.connect_ex.assert_called_with(("127.0.0.1", 5432))

    def test_tailscale_interface_detection(self):
        svc = {"id": "ts", "name": "Tailscale", "type": "Mesh", "check_type": "tailscale"}
        with patch("psutil.net_if_addrs", return_value={"tailscale0": []}):
            self.assertEqual(service_checker.check_single_service(svc)["status"], "online")
        with patch("psutil.net_if_addrs", return_value={"eth0": []}):
            self.assertEqual(service_checker.check_single_service(svc)["status"], "offline")

    def test_get_services_status_checks_every_service(self):
        fake_matrix = [{"id": str(i)} for i in range(4)]
        with patch.object(service_checker, "SERVICES_MATRIX", fake_matrix), \
             patch.object(service_checker, "check_single_service", side_effect=lambda s: {"id": s["id"], "status": "online"}):
            results = service_checker.get_services_status()
        self.assertEqual([r["id"] for r in results], ["0", "1", "2", "3"])


class TestDiagnostics(unittest.TestCase):
    """run_diagnostics with every input mocked so each verdict is deterministic."""

    def run_with(self, disks=None, mem_pct=40.0, temp=50.0, services=None, wsl=False, cron_exists=True):
        disks = disks if disks is not None else [{"mount_point": "/", "percent": 40.0, "free_formatted": "60 GB"}]
        services = services if services is not None else [{"name": "A", "status": "online"}]
        with patch.object(service_checker, "get_storage_info", return_value=disks), \
             patch.object(service_checker, "get_memory_info", return_value={"percent": mem_pct, "available_formatted": "1 GB"}), \
             patch.object(service_checker, "get_cpu_info", return_value={"temperature_c": temp, "load_percent": 5}), \
             patch.object(service_checker, "get_services_status", return_value=services), \
             patch.object(service_checker, "is_wsl_environment", return_value=wsl), \
             patch("os.path.exists", return_value=cron_exists), \
             patch("os.path.getmtime", return_value=1_700_000_000):
            return service_checker.run_diagnostics()

    def statuses(self, report, category):
        return [c["status"] for c in report["checks"] if c["category"] == category]

    def test_all_nominal(self):
        report = self.run_with()
        self.assertEqual(report["overall_status"], "All Systems Nominal")
        self.assertEqual(report["overall_badge_class"], "badge-nominal")
        self.assertEqual((report["critical_count"], report["warning_count"]), (0, 0))
        self.assertEqual(report["total_checks"], len(report["checks"]))

    def test_critical_disk_dominates_summary(self):
        report = self.run_with(disks=[
            {"mount_point": "/a", "percent": 96.0}, {"mount_point": "/b", "percent": 99.0},
            {"mount_point": "/c", "percent": 92.0},
        ])
        self.assertEqual(self.statuses(report, "Storage"), ["CRITICAL", "CRITICAL", "WARNING"])
        self.assertEqual(report["overall_status"], "2 Critical Storage Alerts")
        self.assertEqual(report["overall_badge_class"], "badge-critical")

    def test_single_critical_is_singular(self):
        report = self.run_with(disks=[{"mount_point": "/a", "percent": 96.0}])
        self.assertEqual(report["overall_status"], "1 Critical Storage Alert")

    def test_memory_and_temperature_warnings(self):
        report = self.run_with(mem_pct=95.0, temp=85.0)
        self.assertEqual(self.statuses(report, "Memory"), ["WARNING"])
        self.assertEqual(self.statuses(report, "CPU Thermal"), ["WARNING"])
        self.assertEqual(report["overall_status"], "2 Warnings Detected")
        self.assertEqual(report["overall_badge_class"], "badge-warning")

    def test_service_outage_warns_in_production_but_not_in_wsl(self):
        down = [{"name": "A", "status": "online"}, {"name": "B", "status": "offline"}]
        prod = self.run_with(services=down, wsl=False)
        self.assertEqual(self.statuses(prod, "Services Matrix"), ["WARNING"])
        self.assertEqual(prod["warning_count"], 1)
        dev = self.run_with(services=down, wsl=True)
        self.assertEqual(self.statuses(dev, "Services Matrix"), ["INFO"])
        self.assertEqual(dev["warning_count"], 0)

    def test_cron_logs_pass_when_present_and_info_when_missing(self):
        present = self.run_with(cron_exists=True)
        self.assertTrue(all(s == "PASS" for s in self.statuses(present, "Automation")))
        missing = self.run_with(cron_exists=False)
        self.assertTrue(all(s == "INFO" for s in self.statuses(missing, "Automation")))
        self.assertEqual(len(self.statuses(missing, "Automation")), len(monitor_config.CRON_LOGS))


class TestMonitorRoutes(unittest.TestCase):

    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(monitoring_bp)
        self.client = app.test_client()

    def test_dashboard_renders(self):
        resp = self.client.get("/monitoring")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"<html", resp.data.lower())

    def test_json_endpoints_delegate_to_collectors(self):
        cases = [
            ("/api/monitoring/system", "collect_system_telemetry", {"hostname": "box"}),
            ("/api/monitoring/storage", "get_storage_info", [{"name": "OS Root"}]),
            ("/api/monitoring/services", "get_services_status", [{"id": "immich"}]),
            ("/api/monitoring/diagnostics", "run_diagnostics", {"overall_status": "ok"}),
        ]
        for url, func, payload in cases:
            with patch(f"modules.Monitor.routes.{func}", return_value=payload):
                resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200, url)
            self.assertEqual(resp.get_json(), payload, url)

    def test_processes_passes_sort_and_limit(self):
        with patch("modules.Monitor.routes.get_top_processes", return_value={"processes": []}) as top:
            self.client.get("/api/monitoring/processes?sort=CPU&limit=3")
            top.assert_called_with(sort_by="cpu", limit=3)
            self.client.get("/api/monitoring/processes")
            top.assert_called_with(sort_by="ram", limit=10)
            self.client.get("/api/monitoring/processes?limit=abc")
            top.assert_called_with(sort_by="ram", limit=10)


if __name__ == "__main__":
    unittest.main()
