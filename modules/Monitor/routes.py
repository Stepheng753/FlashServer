from flask import Blueprint, jsonify, render_template, request
from .collectors.system_collector import collect_system_telemetry, get_storage_info
from .collectors.process_collector import get_top_processes
from .collectors.service_checker import get_services_status, run_diagnostics
from .config import is_wsl_environment

monitoring_bp = Blueprint('monitoring', __name__, template_folder='.')


@monitoring_bp.route("/monitoring")
def monitoring_dashboard():
    """Renders the interactive System Health & Operational Telemetry dashboard."""
    is_wsl = is_wsl_environment()
    return render_template("monitoring.html", is_wsl=is_wsl)


@monitoring_bp.route("/api/monitoring/system")
def api_system():
    """Returns live hardware specifications and CPU/RAM/Host telemetry."""
    data = collect_system_telemetry()
    return jsonify(data)


@monitoring_bp.route("/api/monitoring/processes")
def api_processes():
    """Returns top processes sorted by RAM or CPU utilization."""
    sort_by = request.args.get('sort', 'ram').lower()
    try:
        limit = int(request.args.get('limit', 10))
    except ValueError:
        limit = 10

    data = get_top_processes(sort_by=sort_by, limit=limit)
    return jsonify(data)


@monitoring_bp.route("/api/monitoring/storage")
def api_storage():
    """Returns live storage mounts and flash-server network shares."""
    return jsonify(get_storage_info())


@monitoring_bp.route("/api/monitoring/services")
def api_services():
    """Returns live health status of all flash-server services and Docker containers."""
    return jsonify(get_services_status())


@monitoring_bp.route("/api/monitoring/diagnostics")
def api_diagnostics():
    """Executes live diagnostic test suite and returns itemized audit."""
    return jsonify(run_diagnostics())
