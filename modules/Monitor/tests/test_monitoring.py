import os
import sys
import unittest

# Add repo root to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from modules.Monitor.collectors.system_collector import (
    collect_system_telemetry,
    get_cpu_info,
    get_memory_info,
    get_storage_info,
    format_bytes
)
from modules.Monitor.collectors.process_collector import get_top_processes
from modules.Monitor.collectors.service_checker import run_diagnostics
from modules.Monitor.config import SERVICES_MATRIX, STORAGE_MOUNTS


class MonitoringTestCase(unittest.TestCase):

    def test_system_telemetry(self):
        metrics = collect_system_telemetry()
        self.assertIn("hostname", metrics)
        self.assertIn("cpu", metrics)
        self.assertIn("memory", metrics)
        self.assertIn("cores_logical", metrics["cpu"])
        self.assertGreater(metrics["cpu"]["cores_logical"], 0)

    def test_cpu_and_memory_info(self):
        cpu = get_cpu_info()
        self.assertIn("model", cpu)
        self.assertIn("load_percent", cpu)

        mem = get_memory_info()
        self.assertIn("total_formatted", mem)
        self.assertIn("used_formatted", mem)

    def test_process_collector(self):
        res_ram = get_top_processes(sort_by="ram", limit=5)
        self.assertIsInstance(res_ram, dict)
        self.assertIn("processes", res_ram)
        self.assertLessEqual(len(res_ram["processes"]), 5)
        if res_ram["processes"]:
            self.assertIn("pid", res_ram["processes"][0])
            self.assertIn("name", res_ram["processes"][0])

        res_cpu = get_top_processes(sort_by="cpu", limit=5)
        self.assertIsInstance(res_cpu, dict)
        self.assertIn("processes", res_cpu)
        self.assertLessEqual(len(res_cpu["processes"]), 5)

    def test_storage_info(self):
        storage = get_storage_info()
        self.assertIsInstance(storage, list)
        self.assertGreater(len(storage), 0)
        self.assertIn("name", storage[0])
        self.assertIn("percent", storage[0])

    def test_diagnostic_tests(self):
        diag = run_diagnostics()
        self.assertIn("overall_status", diag)
        self.assertIn("total_checks", diag)
        self.assertIn("checks", diag)
        self.assertIsInstance(diag["checks"], list)

    def test_format_bytes(self):
        self.assertEqual(format_bytes(0), "0.0 B")
        self.assertEqual(format_bytes(1024), "1.0 KB")
        self.assertEqual(format_bytes(1048576), "1.0 MB")
        self.assertEqual(format_bytes(1073741824), "1.0 GB")

    def test_config_structures(self):
        self.assertIsInstance(SERVICES_MATRIX, list)
        self.assertGreater(len(SERVICES_MATRIX), 0)
        self.assertIsInstance(STORAGE_MOUNTS, list)
        self.assertGreater(len(STORAGE_MOUNTS), 0)


if __name__ == "__main__":
    unittest.main()
