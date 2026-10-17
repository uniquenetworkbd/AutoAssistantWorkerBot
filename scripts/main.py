"""Master controller for AutoAssistantWorkerBot."""
from __future__ import annotations

import traceback
from datetime import datetime, timezone

from notifier import send_alert, send_document
from scraper import run


def main() -> int:
    started = datetime.now(timezone.utc)
    try:
        report = run()
        send_document(report, f"AutoAssistantWorkerBot report — {report.name}")
        print(f"SUCCESS: {report}")
        print(f"Started: {started.isoformat()}  Finished: {datetime.now(timezone.utc).isoformat()}")
        return 0
    except Exception as exc:
        message = "AutoAssistantWorkerBot FAILED\n\n" + str(exc) + "\n\n" + traceback.format_exc(limit=10)
        print(message)
        send_alert(message)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
