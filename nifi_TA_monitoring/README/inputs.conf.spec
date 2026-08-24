[nifi://<name>]
*This is how the NiFi capture is configured

api_url = <value>
*This is the nifi api url base with port and nifi-api

endpoint_system_diagnostics = <value>
*Enable Enpoint for system diagnostics

endpoint_flow_status = <value>
*Enable Enpoint for flow status

endpoint_processors_history = <value>
*Enable Enpoint for processor history

endpoint_process_groups_history = <value>
*Enable Enpoint for processor history

endpoint_flow_metrics = <value>
*Collect flow metrics from /flow/metrics/json [0 | 1]. NiFi 1.16 and later. Defaults to 0.

metrics_registries = <value>
*Registries to collect, comma separated. Empty collects all.

metrics_strategy = <value>
*ALL_PROCESS_GROUPS (default) or ALL_COMPONENTS.

metrics_sample_filter = <value>
*Regular expression matched against the metric name.

endpoint_bulletin_board = <value>
*Poll the bulletin board for individual bulletins [0 | 1]. Defaults to 1.

auth_type = <value>
*Authentication type [none | basic ]

username = <value>
*Authentication user

password = <value>
*Authentication password

interval = <value>
*Seconds betwen each execution

host = <value>
*Hostname NiFi instance

verify_tls = <value>
*Verify the NiFi TLS certificate [0 | 1]. Defaults to 1 (verify).

ca_bundle = <value>
*Path to a CA bundle used to verify the NiFi certificate. Empty uses the system trust store.
