import psutil
from .system_collector import format_bytes


def get_top_processes(sort_by: str = "ram", limit: int = 10) -> dict:
    """
    Returns top processes sorted by RAM or CPU utilization.
    Guarded against AccessDenied and NoSuchProcess exceptions.
    """
    procs = []
    total_rss = 0
    total_procs_count = 0

    attrs = ['pid', 'name', 'username', 'memory_info', 'memory_percent', 'cpu_percent', 'cmdline']
    for proc in psutil.process_iter(attrs):
        total_procs_count += 1
        try:
            p_info = proc.info
            mem_info = p_info.get('memory_info')
            rss_bytes = mem_info.rss if mem_info else 0
            total_rss += rss_bytes

            # Command line formatting
            cmd_list = p_info.get('cmdline')
            if cmd_list and len(cmd_list) > 0:
                full_cmd = " ".join(cmd_list)
            else:
                full_cmd = p_info.get('name') or "Unknown"

            username = p_info.get('username') or "system"
            formatted_mem = format_bytes(rss_bytes)
            mem_pct = round(p_info.get('memory_percent') or 0.0, 1)

            procs.append({
                "pid": p_info.get('pid'),
                "name": p_info.get('name') or "Unknown",
                "username": username,
                "user": username,
                "rss_bytes": rss_bytes,
                "rss_formatted": formatted_mem,
                "ram_rss_formatted": formatted_mem,
                "memory_percent": mem_pct,
                "ram_percent": mem_pct,
                "cpu_percent": round(p_info.get('cpu_percent') or 0.0, 1),
                "cmdline": full_cmd
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    # Sorting
    if sort_by.lower() == "cpu":
        procs.sort(key=lambda x: x["cpu_percent"], reverse=True)
    else:  # default 'ram'
        procs.sort(key=lambda x: x["rss_bytes"], reverse=True)

    top_n = procs[:limit]

    # Add 1-indexed rank
    for rank, p in enumerate(top_n, start=1):
        p["rank"] = rank

    formatted_total_rss = format_bytes(total_rss)

    return {
        "sort_by": sort_by,
        "limit": limit,
        "total_processes_count": total_procs_count,
        "total_rss_bytes": total_rss,
        "total_rss_formatted": formatted_total_rss,
        "ram_in_use_formatted": formatted_total_rss,
        "processes": top_n
    }
