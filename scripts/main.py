"""Master controller for AutoAssistantWorkerBot."""
from __future__ import annotations

import traceback
from datetime import datetime, timezone

from notifier import record_error, send_alert, send_report
from scraper import run


def main() -> int:
    started = datetime.now(timezone.utc)
    try:
        report = run()
        for target in report.get("targets", []):
            if target.get("status") != "success":
                record_error(
                    "target_execution",
                    RuntimeError(target.get("error") or "Target failed"),
                    site_key=target.get("site_key"),
                    url=target.get("url"),
                )

        send_report(report)
        status = report.get("status", "unknown")
        print(f"{status.upper()}: {report}")
        print(f"Started: {started.isoformat()}  Finished: {datetime.now(timezone.utc).isoformat()}")

        if status != "success":
            send_alert(
                f"AutoAssistantWorkerBot {status.upper()}\n"
                f"Successful targets: {report.get('success_count', 0)}\n"
                f"Failed targets: {report.get('failure_count', 0)}"
            )
            return 1
        return 0
    except Exception as exc:
        record_error("master_controller", exc)
        message = "AutoAssistantWorkerBot FAILED\n\n" + str(exc) + "\n\n" + traceback.format_exc(limit=10)
        print(message)
        send_alert(message)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
