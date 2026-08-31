def format_control_summary(health: dict) -> str:
    modules = health.get("modules", {})

    def s(name, default="UNKNOWN"):
        return modules.get(name, {}).get("status", default)

    lines = [
        "PROJECT_EZ_Culture HEALTH",
        "",
        f"CHECK_TIME: {health.get('generated_at', 'UNKNOWN')}",
        f"SYSTEM_HEALTH: {health.get('system_health_status', 'UNKNOWN')}",
        f"DELIVERY_LIFECYCLE: {health.get('delivery_lifecycle_status', 'UNKNOWN')}",
        f"GITHUB: {s('github')}",
        f"FDRIVE: {s('fdrive')}",
        f"RECOVERY_BASELINE: {s('recovery_baseline')}",
        f"MT5_RUNTIME_BASELINE: {s('mt5_runtime_baseline')}",
        f"SIGNAL: {s('signal')}",
        f"GENERATEDTIME: {s('generatedtime', 'PENDING_VALIDATION')}",
        f"MARKET_DATA: {s('market_data')}",
        f"DRIVE_DELIVERY: {s('drive_delivery')}",
        f"CONTROL_REVIEW: {s('control_review')}",
        f"USER_REPORT: {s('user_report')}",
        f"SCHEDULER: {s('scheduler')}",
        f"COMPILE: {s('compile', 'NOT_REQUESTED')}",
        f"DEPLOYMENT: {s('deployment', 'NOT_REQUESTED')}",
        f"BROKER_SEPARATION: {s('broker_separation')}",
        f"CRITICAL_ALERT: {'NONE' if not health.get('alerts') else '; '.join(health['alerts'])}",
        f"RECOVERY_REQUIRED: {modules.get('mt5_runtime_baseline', {}).get('recovery_required', False)}",
        f"TASK_CANDIDATE: {'NONE' if not health.get('task_candidates') else '; '.join(health['task_candidates'])}",
    ]
    return "\n".join(lines)
