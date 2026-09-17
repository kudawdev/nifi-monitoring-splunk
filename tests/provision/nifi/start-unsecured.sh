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

# A clustered node must advertise a host others can reach: NiFi builds the URI
# it replicates a request to from the *web* host, not from
# nifi.cluster.node.address, so 0.0.0.0 -- fine on a single node -- makes the
# coordinator call http://0.0.0.0:8080/... and answer HTTP 500. Binding to the
# container's own name still works through a published port.
if [ "${NIFI_CLUSTER_IS_NODE:-false}" = "true" ]; then
    # Deliberately ignores an explicit 0.0.0.0: the profiles set it in their
    # env file for the single-node case, and inheriting it here brings the
    # replication failure back. Clustering decides this, not the caller.
    if [ -z "${NIFI_WEB_HTTP_HOST:-}" ] || [ "${NIFI_WEB_HTTP_HOST}" = "0.0.0.0" ]; then
        prop_replace 'nifi.web.http.host' "$HOSTNAME"
    else
        prop_replace 'nifi.web.http.host' "${NIFI_WEB_HTTP_HOST}"
    fi
else
    prop_replace 'nifi.web.http.host' "${NIFI_WEB_HTTP_HOST:-0.0.0.0}"
fi

# No authentication: over HTTP NiFi authenticates nobody and authorises
# everyone, which is why this is a test-only arrangement.
prop_replace 'nifi.security.user.login.identity.provider' ''
prop_replace 'nifi.security.keystore'   ''
prop_replace 'nifi.security.truststore' ''
prop_replace 'nifi.remote.input.secure' 'false'
prop_replace 'nifi.remote.input.host'   "${HOSTNAME}"

# Clustering, when the profile asks for it. The image's start.sh maps these
# from NIFI_CLUSTER_* / NIFI_ZK_*, and this entrypoint replaces it, so the
# same mapping has to happen here. The cluster protocol runs unsecured for the
# same reason the web port does: a secured cluster needs a certificate per
# node, which is a different exercise from proving the add-on reads one.
if [ "${NIFI_CLUSTER_IS_NODE:-false}" = "true" ]; then
    prop_replace 'nifi.cluster.is.node'                     'true'
    prop_replace 'nifi.cluster.node.address'                "${NIFI_CLUSTER_ADDRESS:-$HOSTNAME}"
    prop_replace 'nifi.cluster.node.protocol.port'          "${NIFI_CLUSTER_NODE_PROTOCOL_PORT:-8082}"
    prop_replace 'nifi.cluster.protocol.is.secure'          'false'
    prop_replace 'nifi.zookeeper.connect.string'            "${NIFI_ZK_CONNECT_STRING:-}"
    prop_replace 'nifi.zookeeper.root.node'                 "${NIFI_ZK_ROOT_NODE:-/nifi}"
    prop_replace 'nifi.cluster.flow.election.max.wait.time' "${NIFI_ELECTION_MAX_WAIT:-1 min}"
    prop_replace 'nifi.cluster.flow.election.max.candidates' "${NIFI_ELECTION_MAX_CANDIDATES:-2}"
    prop_replace 'nifi.state.management.provider.cluster'   'zk-provider'
    # A clustered NiFi refuses to start without this, and every node needs the
    # SAME value: "Clustered Configuration Found: Shared Sensitive Properties
    # Key [nifi.sensitive.props.key] required". A single node does not need it,
    # which is why it only shows up here.
    prop_replace 'nifi.sensitive.props.key' "${NIFI_SENSITIVE_PROPS_KEY:-harness-shared-sensitive-key}"
    . "${scripts_dir}/update_cluster_state_management.sh"
    echo "clustering as ${NIFI_CLUSTER_ADDRESS:-$HOSTNAME} against ZooKeeper ${NIFI_ZK_CONNECT_STRING:-}"
fi

# Same two lines the image's start.sh uses to enable the Python extensions.
uncomment "nifi.python.command" ${nifi_props_file}
prop_replace 'nifi.nar.library.autoload.directory' "${NIFI_HOME}/nar_extensions"

echo "starting NiFi on http://${NIFI_WEB_HTTP_HOST:-0.0.0.0}:${NIFI_WEB_HTTP_PORT:-8080} with no authentication"
exec "${NIFI_HOME}/bin/nifi.sh" run
