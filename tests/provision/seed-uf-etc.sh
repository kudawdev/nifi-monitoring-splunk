#!/bin/sh
# Seed /opt/splunkforwarder/etc before the Universal Forwarder's first boot.
#
# Same trick as seed-splunk-etc.sh: the image extracts its own etc/
# additively on first start, so what is placed here survives.
#
# The forwarder gets the real TA, not a bespoke inputs.conf, so the profile
# exercises the monitor stanzas as shipped. Only `disabled` and `index` are
# overridden, in local/.
#
# Runs in a busybox container: POSIX sh only, no bash.

set -eu

SEED=/etc-seed
SRC=/src

echo "seed-uf: installing the TA"
mkdir -p "$SEED/apps"
rm -rf "$SEED/apps/nifi_TA_monitoring"
cp -r "$SRC/nifi_TA_monitoring" "$SEED/apps/nifi_TA_monitoring"
find "$SEED/apps/nifi_TA_monitoring" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

# A forwarder must not run the modular input: that is the indexer's job here,
# and two collectors would duplicate every API event.
mkdir -p "$SEED/apps/nifi_TA_monitoring/local"
echo "seed-uf: enabling the log monitors, leaving the modular input off"
cp "$SRC/tests/provision/uf/inputs.conf" \
   "$SEED/apps/nifi_TA_monitoring/local/inputs.conf"

echo "seed-uf: pointing outputs at the indexer"
mkdir -p "$SEED/system/local"
cat > "$SEED/system/local/outputs.conf" <<'CONF'
[tcpout]
defaultGroup = indexer

[tcpout:indexer]
server = splunk:9997

[tcpout-server://splunk:9997]
CONF

# Ownership: the forwarder image runs as uid 41812 (user "splunk").
chown -R 41812:41812 "$SEED" 2>/dev/null || true

echo "seed-uf: done"
