#!/usr/bin/env python3
"""Enable the alerts the app ships, for run.sh --showcase.

The app ships every alert disabled, so the Alerts view of a fresh install
reads "0 enabled". The showcase environment turns them on, the way a user
would after installing, so its screenshot shows them enabled and, on a
healthy fleet, none fired.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from support import connect  # noqa: E402

APP = "nifi_monitoring"


def main():
    service = connect(app=APP, owner="nobody")
    alerts = [s for s in service.saved_searches
              if s.access["app"] == APP and s.name.startswith("NiFi - ")]
    for alert in alerts:
        alert.enable()
        print("    enabled: %s" % alert.name)
    return 0 if alerts else 1


if __name__ == "__main__":
    sys.exit(main())
