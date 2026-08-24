#!/usr/bin/env python3
"""Load the `instance` KV store collection.

nifi_monitoring's transforms.conf declares the `instance` lookup with
`external_type = kvstore` and `collection = instance`, so it is backed by the
KV store, not by a CSV. Dropping a file into lookups/ does nothing: the rows
have to be written into the collection, which only exists once splunkd is
running.

Run by run.sh after the stack is up. Idempotent.
"""

import csv
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from support import TESTS_DIR, connect  # noqa: E402

COLLECTION = "instance"
APP = "nifi_monitoring"
SOURCE = os.path.join(TESTS_DIR, "provision", "splunk", "instance.csv")


def wait_for_kvstore(service, timeout=300, interval=5):
    """Block until the KV store reports ready.

    splunkd answers its healthcheck before the KV store finishes coming up,
    so writing straight away gets 'HTTP 503 KV Store is initializing'. Only
    shows up when the steps run back to back, which is exactly what CI does.
    """
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            body = service.get("/services/kvstore/status", output_mode="json").body
            status = json.loads(body.read().decode())["entry"][0]["content"]
            last = status.get("current", {}).get("status", status)
            if last == "ready":
                return True
        except Exception as error:  # noqa: BLE001 - keep polling through hiccups
            last = error
        time.sleep(interval)
    print("kvstore did not become ready within %ds (last: %s)" % (timeout, last),
          file=sys.stderr)
    return False


def main():
    # The collection lives in the app's namespace, so connect scoped to it.
    service = connect(app=APP, owner="nobody")

    if not wait_for_kvstore(service):
        return 1

    try:
        collection = service.kvstore[COLLECTION]
    except KeyError:
        print(
            "kvstore collection '%s' not found in app '%s'; is the app installed?"
            % (COLLECTION, APP),
            file=sys.stderr,
        )
        return 1

    with open(SOURCE) as handle:
        rows = list(csv.DictReader(handle))

    for row in rows:
        record = {k: v for k, v in row.items() if v not in (None, "")}
        key = record.pop("_key", None) or record["host"]
        # Upsert so re-running against a live stack is harmless.
        try:
            collection.data.delete_by_id(key)
        except Exception:  # noqa: BLE001 - absent record is the normal case
            pass
        record["_key"] = key
        collection.data.insert(record)
        print("    instance: %s -> cluster=%s" % (key, record.get("cluster")))

    loaded = collection.data.query()
    print("    %d row(s) in the %s collection" % (len(loaded), COLLECTION))
    return 0 if loaded else 1


if __name__ == "__main__":
    sys.exit(main())
