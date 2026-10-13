# Monitor Testing

Tests: [modules/Monitor/tests/](../../modules/Monitor/tests/)

```bash
.venv/bin/python -m unittest discover -s modules/Monitor/tests -p "test_*.py"
```

Neither file needs a database or credentials.

## `test_monitoring.py` (smoke tests against the real host)

These call the collectors for real, so results depend on the machine. They only check structure, not health: a laptop can warn on storage and still pass.

| Test | What it checks |
| :--- | :--- |
| `test_system_telemetry`, `test_cpu_and_memory_info` | Output has the expected keys (hostname, cpu, memory) and a positive logical core count. |
| `test_process_collector` | `get_top_processes` honors `limit` for both `ram` and `cpu` sorting. |
| `test_storage_info` | Returns a non-empty list whose entries have `name` and `percent`. |
| `test_diagnostic_tests` | `run_diagnostics()` returns `overall_status`, `total_checks` and a `checks` list. |
| `test_format_bytes`, `test_config_structures` | Helper output and well-formed `SERVICES_MATRIX` / `STORAGE_MOUNTS`. |

## `test_monitor_logic.py` (deterministic, everything mocked)

`psutil`, sockets, `urllib`, the filesystem and the environment are all patched, so these pass identically anywhere.

| Class | What it checks |
| :--- | :--- |
| `TestFormatBytes`, `TestWslDetection` | Unit boundaries and the PB cap. WSL detection from `/proc/version`, native Linux, and the env var fallback. |
| `TestSystemCollectors` | Uptime formatting, memory success and failure, CPU temperature and load average fallbacks, Tailscale IP discovery, OS name parsing, environment label. |
| `TestStorageInfo` | Healthy / High Usage / Near Full thresholds, a mount that does not exist, an unreadable mount, the separate `/home` partition. |
| `TestProcessCollector` | RAM and CPU sorting, ranks, totals, `AccessDenied` processes skipped, command line and username fallbacks. |
| `TestServiceChecker` | HTTP 200 online, 401 still online, connection refused offline, TCP open and closed, Tailscale interface, parallel checking of every service. |
| `TestDiagnostics` | Verdict for each condition: all nominal, one or more critical disks (singular and plural wording), memory and temperature warnings, a service outage (warning in production, info in WSL), cron log present or missing. |
| `TestMonitorRoutes` | Dashboard renders. Each JSON endpoint returns what its collector returned. `/processes` passes `sort` and `limit`, and ignores a non-numeric `limit`. |
