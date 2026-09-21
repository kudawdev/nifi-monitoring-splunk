#!/bin/sh
# Build nifi_TA_monitoring into output/ with ucc-gen.
#
# Since the UCC migration the add-on is generated: app.conf, inputs.conf, the
# spec, restmap.conf and the whole configuration UI do not exist in the tree.
# Seeding a container from nifi_TA_monitoring/ would install something that
# has never been built and is missing every one of them, so both run.sh and
# CI call this first. Condition UI-3 of the plan: what we test is what ships.
#
# Creates its own virtualenv the first time. ucc-gen needs pip to install the
# add-on's own requirements into output/lib, which is why the venv carries
# pip even though uv does not need it.

set -eu

HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(dirname "$HERE")
VENV="$REPO/.venv-ucc"
UCC_VERSION="${UCC_VERSION:-6.6.0}"

cd "$REPO"

if [ ! -x "$VENV/bin/ucc-gen" ]; then
    echo "==> creating $VENV with ucc-gen $UCC_VERSION"
    if command -v uv >/dev/null 2>&1; then
        uv venv --python 3.13 "$VENV"
        uv pip install --python "$VENV" \
            "splunk-add-on-ucc-framework==$UCC_VERSION" pip
    else
        python3 -m venv "$VENV"
        "$VENV/bin/pip" install --quiet --upgrade pip
        "$VENV/bin/pip" install --quiet \
            "splunk-add-on-ucc-framework==$UCC_VERSION"
    fi
fi

VERSION=$(sed -n 's/^ *"version": *"\([0-9][^"]*\)".*/\1/p' \
    nifi_TA_monitoring/globalConfig.json | head -1)
echo "==> building nifi_TA_monitoring $VERSION into output/"

"$VENV/bin/ucc-gen" build \
    --source nifi_TA_monitoring/package \
    --config nifi_TA_monitoring/globalConfig.json \
    --output output \
    --ta-version "$VERSION" \
    --python-binary-name "$VENV/bin/python" \
    --overwrite

# ucc-gen is happy to produce an add-on whose input has no defaults, which is
# the failure additional_packaging.py exists to prevent. Check rather than
# trust: a silent one here means every profile runs with verify_tls off.
for key in python.required verify_tls monitor:///opt/nifi; do
    if ! grep -q "$key" output/nifi_TA_monitoring/default/inputs.conf; then
        echo "build-ta: FATAL generated inputs.conf has no '$key'" >&2
        exit 1
    fi
done

echo "==> built $(du -sh output/nifi_TA_monitoring | cut -f1)"
