#!/bin/sh
# Export the certificate NiFi generates for itself, so the add-on can verify
# the connection instead of being told to skip verification.
#
# Defect R-8: every profile ran with verify_tls = 0 because the containers use
# self-signed certificates, which meant the path 2.0.0 made the default -- TLS
# verification on -- was the one path nothing exercised.
#
# The certificate is self-signed, so it is its own CA: handing this file to
# requests as the bundle is what a real deployment does with a private CA.
# NiFi issues it with SAN DNS:localhost and DNS:nifi, and the add-on connects
# to https://nifi:8443, so the name matches.
#
# Runs in a busybox container with openssl: POSIX sh only.

set -eu

TARGET=/certs/nifi.pem
HOST="${NIFI_HOST:-nifi}"
PORT="${NIFI_PORT:-8443}"

echo "cert: waiting for $HOST:$PORT to present a certificate"
i=0
while [ "$i" -lt 120 ]; do
    if openssl s_client -connect "$HOST:$PORT" -servername "$HOST" </dev/null 2>/dev/null \
        | openssl x509 > "$TARGET.tmp" 2>/dev/null; then
        if [ -s "$TARGET.tmp" ]; then
            mv "$TARGET.tmp" "$TARGET"
            echo "cert: wrote $TARGET"
            openssl x509 -in "$TARGET" -noout -subject -ext subjectAltName 2>/dev/null | sed 's/^/cert:   /'
            chmod a+r "$TARGET"
            # Stays alive on purpose. `docker compose up --wait` treats a
            # container that exits as a failed start unless another service
            # depends on it with service_completed_successfully, and nothing
            # else lives in this compose profile. Sleeping with a healthcheck
            # over the file makes "ready" mean "the certificate is there",
            # which is what the rest of the stack actually waits for.
            exec sleep infinity
        fi
    fi
    i=$((i + 1))
    sleep 5
done

echo "cert: FATAL no certificate from $HOST:$PORT after 10 minutes" >&2
exit 1
