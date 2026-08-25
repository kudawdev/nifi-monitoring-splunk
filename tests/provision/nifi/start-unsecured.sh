#!/bin/sh -e
# Start NiFi 2.x on plain HTTP with no authentication.
#
# The image's own start.sh cannot do this. It writes
#
#   prop_replace 'nifi.web.https.port' "${NIFI_WEB_HTTPS_PORT:-8443}"
#
# and ${VAR:-default} substitutes the default for an empty value as well as an
# unset one, so there is no environment variable that clears it: NiFi comes up
# on HTTPS no matter what the HTTP settings say.
#
# This replaces the entrypoint and does the minimum a throwaway instance
# needs. It is only for the test harness -- an unauthenticated NiFi grants
# every caller every permission.

scripts_dir='/opt/nifi/scripts'
. "${scripts_dir}/common.sh"

# Clear HTTPS so the HTTP listener is the one that binds.
prop_replace 'nifi.web.https.port'  ''
prop_replace 'nifi.web.https.host'  ''
prop_replace 'nifi.web.http.port'   "${NIFI_WEB_HTTP_PORT:-8080}"
prop_replace 'nifi.web.http.host'   "${NIFI_WEB_HTTP_HOST:-0.0.0.0}"

# No authentication: over HTTP NiFi authenticates nobody and authorises
# everyone, which is why this is a test-only arrangement.
prop_replace 'nifi.security.user.login.identity.provider' ''
prop_replace 'nifi.security.keystore'   ''
prop_replace 'nifi.security.truststore' ''
prop_replace 'nifi.remote.input.secure' 'false'
prop_replace 'nifi.remote.input.host'   "${HOSTNAME}"

# Same two lines the image's start.sh uses to enable the Python extensions.
uncomment "nifi.python.command" ${nifi_props_file}
prop_replace 'nifi.nar.library.autoload.directory' "${NIFI_HOME}/nar_extensions"

echo "starting NiFi on http://${NIFI_WEB_HTTP_HOST:-0.0.0.0}:${NIFI_WEB_HTTP_PORT:-8080} with no authentication"
exec "${NIFI_HOME}/bin/nifi.sh" run
