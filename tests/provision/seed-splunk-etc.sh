#!/bin/sh
# Seed /opt/splunk/etc before splunkd's first boot.
#
# The Splunk image extracts its own etc/ additively on first start, so files
# placed here survive. Seeding beforehand replaces the manual step the old
# harness required (docker exec into the container, copy the apps by hand,
# then turn off SSL on the HEC in the UI).
#
# Runs in a busybox container: POSIX sh only, no bash.

set -eu

SEED=/etc-seed
SRC=/src

echo "seed: installing apps"
mkdir -p "$SEED/apps"
for app in nifi_monitoring nifi_TA_monitoring; do
    rm -rf "$SEED/apps/$app"
    cp -r "$SRC/$app" "$SEED/apps/$app"
    # __pycache__ from a host-side test run must not reach the container
    find "$SEED/apps/$app" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
    echo "seed:   $app"
done

echo "seed: installing bundled third-party apps"
for tgz in "$SRC"/tests/additional_apps/*.tgz; do
    [ -f "$tgz" ] || continue
    tar -xzf "$tgz" -C "$SEED/apps"
    echo "seed:   $(basename "$tgz")"
done

echo "seed: enabling HEC without SSL"
# The documented workaround was to turn this off by hand in the UI after
# every start. Doing it in system/local makes the environment reproducible.
mkdir -p "$SEED/system/local"
cat > "$SEED/system/local/inputs.conf" <<'EOF'
[http]
disabled = 0
enableSSL = 0
port = 8088

[http://nifi]
disabled = 0
token = 00000000-0000-0000-0000-0000000000ab
index = main
EOF

echo "seed: configuring the TA input"
mkdir -p "$SEED/apps/nifi_TA_monitoring/local"
if [ -f "$SRC/tests/provision/splunk/inputs.conf" ]; then
    cp "$SRC/tests/provision/splunk/inputs.conf" \
       "$SEED/apps/nifi_TA_monitoring/local/inputs.conf"
fi

echo "seed: seeding the instance lookup"
mkdir -p "$SEED/apps/nifi_monitoring/lookups"
cp "$SRC/tests/provision/splunk/instance.csv" \
   "$SEED/apps/nifi_monitoring/lookups/instance.csv"

# Ownership: the Splunk image runs as uid 41812 (user "splunk").
chown -R 41812:41812 "$SEED" 2>/dev/null || true

echo "seed: done"
