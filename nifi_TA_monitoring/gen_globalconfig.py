"""Generate the globalConfig.json next to this file.

Lives here rather than under a build directory for the same reason
additional_packaging.py does: both are build-time scripts that belong to the
add-on but must stay out of package/, which ucc-gen copies verbatim.

Written as a script rather than hand-edited JSON because the same field list
has to stay consistent across the form, the table and the group layout, and
because a repeated validator block is easier to get wrong than to generate.
Run it, commit the JSON it produces; a unit test fails if they drift.
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "globalConfig.json")

VERSION = "2.0.0"


def length(label, maximum, minimum=1):
    return {
        "type": "string",
        "errorMsg": "Length of %s must be between %d and %d" % (label, minimum, maximum),
        "minLength": minimum,
        "maxLength": maximum,
    }


NAME = {
    "type": "text",
    "label": "NiFi instance name",
    "field": "name",
    "required": True,
    "help": "A unique name for this input. Used as the host value unless one is set below.",
    "validators": [
        {
            "type": "regex",
            "errorMsg": "The name must begin with a letter and contain only letters, digits and underscores.",
            "pattern": "^[a-zA-Z]\\w*$",
        },
        length("the name", 100),
    ],
}

API_URL = {
    "type": "text",
    "label": "NiFi API URL",
    "field": "api_url",
    "required": True,
    "help": "Base URL of the NiFi REST API, e.g. https://nifi-instance:8443/nifi-api/",
    "validators": [
        {
            "type": "regex",
            "errorMsg": "Must be an http:// or https:// URL ending in the NiFi API path.",
            "pattern": "^https?://[^\\s]+$",
        },
        length("the URL", 4096),
    ],
}

AUTH_TYPE = {
    "type": "singleSelect",
    "label": "Authentication",
    "field": "auth_type",
    "required": True,
    "defaultValue": "none",
    "help": "basic performs POST /access/token and sends the JWT it returns.",
    "validators": [
        {
            "type": "regex",
            "errorMsg": "Authentication must be none or basic.",
            "pattern": "^(none|basic)$",
        }
    ],
    "options": {
        "disableSearch": True,
        "autoCompleteFields": [
            {"label": "None", "value": "none"},
            {"label": "Username and password", "value": "basic"},
        ],
    },
    # The credentials are meaningless without basic, and leaving them on
    # screen in `none` invites someone to fill them in and wonder why they are
    # ignored. The legacy manager XML did this with a showonly group; this is
    # the same intent, declared rather than scripted.
    "modifyFieldsOnValue": [
        {
            "fieldValue": "none",
            "fieldsToModify": [
                {"fieldId": "username", "display": False, "required": False},
                {"fieldId": "password", "display": False, "required": False},
            ],
        },
        {
            "fieldValue": "basic",
            "fieldsToModify": [
                {"fieldId": "username", "display": True, "required": True},
                {"fieldId": "password", "display": True, "required": True},
            ],
        },
    ],
}

USERNAME = {
    "type": "text",
    "label": "Username",
    "field": "username",
    "required": False,
    "validators": [length("the username", 200)],
}

PASSWORD = {
    "type": "text",
    "label": "Password",
    "field": "password",
    "required": False,
    "encrypted": True,
    "validators": [length("the password", 8192)],
}

TEST_CONNECTION = {
    "type": "custom",
    "label": "Connection",
    "field": "test_connection",
    "help": "Calls the NiFi API with the values above, without saving them.",
    "options": {
        "type": "external",
        "src": "test_connection",
    },
}

ENDPOINT_CHECKBOXES = [
    ("endpoint_flow_status", "Flow status", "1",
     "GET /flow/status. The summary counters every dashboard panel is built on."),
    ("endpoint_system_diagnostics", "System diagnostics", "1",
     "GET /system-diagnostics. Heap, threads and repository usage. Also how the "
     "add-on detects the NiFi version, so leaving it off disables version "
     "reporting."),
    ("endpoint_bulletin_board", "Bulletin board", "1",
     "GET /flow/bulletin-board. Individual bulletins, polled with a cursor so "
     "nothing is counted twice. The board keeps a short window, so an interval "
     "longer than that window can miss bulletins."),
]

HISTORY_FIELDS = [
    ("endpoint_processors_history", "Processor IDs",
     "UUIDs of the processors to collect status history for, comma or newline "
     "separated. Empty collects none."),
    ("endpoint_process_groups_history", "Process group IDs",
     "UUIDs of the process groups to collect status history for, comma or "
     "newline separated. Empty collects none."),
]

FLOW_METRICS = [
    {
        "type": "checkbox",
        "label": "Collect flow metrics",
        "field": "endpoint_flow_metrics",
        "defaultValue": 0,
        "help": "GET /flow/metrics/json. NiFi 1.16 and later. Off by default: on "
                "a large flow this is the highest-volume endpoint the add-on has.",
        "modifyFieldsOnValue": [
            {
                "fieldValue": 0,
                "fieldsToModify": [
                    {"fieldId": "metrics_registries", "display": False},
                    {"fieldId": "metrics_strategy", "display": False},
                    {"fieldId": "metrics_sample_filter", "display": False},
                ],
            },
            {
                "fieldValue": 1,
                "fieldsToModify": [
                    {"fieldId": "metrics_registries", "display": True},
                    {"fieldId": "metrics_strategy", "display": True},
                    {"fieldId": "metrics_sample_filter", "display": True},
                ],
            },
        ],
    },
    {
        "type": "text",
        "label": "Registries",
        "field": "metrics_registries",
        "required": False,
        "help": "Comma-separated registry names to collect, e.g. NIFI,JVM. Empty "
                "collects every registry NiFi offers.",
        "validators": [length("the registry list", 1024)],
    },
    {
        "type": "singleSelect",
        "label": "Strategy",
        "field": "metrics_strategy",
        "required": False,
        "defaultValue": "ALL_PROCESS_GROUPS",
        "help": "ALL_COMPONENTS emits a sample per component and multiplies the "
                "volume; measure before choosing it.",
        "validators": [
            {
                "type": "regex",
                "errorMsg": "Strategy must be ALL_PROCESS_GROUPS or ALL_COMPONENTS.",
                "pattern": "^(ALL_PROCESS_GROUPS|ALL_COMPONENTS)$",
            }
        ],
        "options": {
            "disableSearch": True,
            "autoCompleteFields": [
                {"label": "All process groups", "value": "ALL_PROCESS_GROUPS"},
                {"label": "All components", "value": "ALL_COMPONENTS"},
            ],
        },
    },
    {
        "type": "text",
        "label": "Sample filter",
        "field": "metrics_sample_filter",
        "required": False,
        "help": "Regular expression matched against the metric name. Empty keeps "
                "every sample.",
        "validators": [length("the filter", 1024)],
    },
]

CUSTOM_ENDPOINTS = {
    "type": "textarea",
    "label": "Additional endpoints",
    "field": "custom_endpoints",
    "required": False,
    "options": {"rowsMin": 3, "rowsMax": 12},
    "help": "One per line, as name,path -- e.g. "
            "queue_stats,/flow/connections/1234-5678-90ab-cdef/status. Each is "
            "indexed under nifi:api:custom:<name>, so that one is searchable "
            "as nifi:api:custom:queue_stats. The path is relative to the API "
            "URL above and is requested exactly as written: no {id} "
            "substitution. A request that fails writes no event, so an empty "
            "sourcetype means the endpoint is not working.",
    "validators": [length("the endpoint list", 16384)],
}

TLS = [
    {
        "type": "checkbox",
        "label": "Verify the TLS certificate",
        "field": "verify_tls",
        "defaultValue": 1,
        "help": "Leave this on unless NiFi uses a certificate that cannot be "
                "trusted through a CA bundle. Turning it off lets anyone able to "
                "intercept the connection read the credentials and the token.",
        "modifyFieldsOnValue": [
            {"fieldValue": 0, "fieldsToModify": [{"fieldId": "ca_bundle", "display": False}]},
            {"fieldValue": 1, "fieldsToModify": [{"fieldId": "ca_bundle", "display": True}]},
        ],
    },
    {
        "type": "text",
        "label": "CA bundle path",
        "field": "ca_bundle",
        "required": False,
        "help": "e.g. /opt/splunk/etc/apps/nifi_TA_monitoring/local/nifi-ca.pem. "
                "Empty uses the system trust store.",
        "validators": [length("the path", 4096)],
    },
]

ADVANCED = [
    {
        "type": "interval",
        "label": "Interval",
        "field": "interval",
        "required": True,
        "defaultValue": "60",
        "help": "Seconds between polls. Every enabled endpoint, including the "
                "custom ones, is collected on this interval.",
    },
    {"type": "index", "label": "Index", "field": "index"},
    {
        "type": "text",
        "label": "Host field value",
        "field": "host",
        "required": False,
        "help": "Stamped on every event from this input. Empty uses the instance "
                "name above. On a cluster set this to the cluster, not a node: "
                "the add-on names the node in a separate field.",
        "validators": [length("the host", 255)],
    },
]


def checkbox(field, label, default, help_text):
    return {
        "type": "checkbox",
        "label": label,
        "field": field,
        "defaultValue": int(default),
        "help": help_text,
    }


def textarea(field, label, help_text):
    return {
        "type": "textarea",
        "label": label,
        "field": field,
        "required": False,
        "options": {"rowsMin": 2, "rowsMax": 10},
        "help": help_text,
        "validators": [length(label, 16384)],
    }


def build():
    entity = [NAME, API_URL, AUTH_TYPE, USERNAME, PASSWORD, TEST_CONNECTION]
    entity += [checkbox(*args) for args in ENDPOINT_CHECKBOXES]
    entity += [textarea(*args) for args in HISTORY_FIELDS]
    entity += FLOW_METRICS
    entity.append(CUSTOM_ENDPOINTS)
    entity += TLS
    entity += ADVANCED

    groups = [
        {"label": "NiFi instance", "fields": ["name", "api_url"]},
        {"label": "Authentication",
         "fields": ["auth_type", "username", "password", "test_connection"]},
        {"label": "Endpoints",
         "fields": [field for field, _, _, _ in ENDPOINT_CHECKBOXES]},
        {"label": "Status history",
         "fields": [field for field, _, _ in HISTORY_FIELDS],
         "options": {"isExpandable": True, "expand": False}},
        {"label": "Flow metrics",
         "fields": [item["field"] for item in FLOW_METRICS],
         "options": {"isExpandable": True, "expand": False}},
        {"label": "Custom endpoints", "fields": ["custom_endpoints"],
         "options": {"isExpandable": True, "expand": False}},
        {"label": "TLS", "fields": [item["field"] for item in TLS],
         "options": {"isExpandable": True, "expand": False}},
        {"label": "Advanced", "fields": [item["field"] for item in ADVANCED],
         "options": {"isExpandable": True, "expand": False}},
    ]

    declared = {item["field"] for item in entity}
    grouped = {field for group in groups for field in group["fields"]}
    assert declared == grouped, "ungrouped: %s" % sorted(declared ^ grouped)

    return {
        "meta": {
            "name": "nifi_TA_monitoring",
            "restRoot": "nifi_TA_monitoring",
            "version": VERSION,
            "displayName": "NiFi TA Monitoring",
            "schemaVersion": "0.0.10",
            "checkForUpdates": True,
            "supportedThemes": ["light", "dark"],
        },
        "pages": {
            "configuration": {
                "title": "Configuration",
                "description": "Add-on wide settings. The NiFi instances "
                               "themselves are configured under Inputs.",
                "tabs": [{"type": "loggingTab"}],
            },
            "inputs": {
                "title": "Inputs",
                "description": "One entry per NiFi instance. A NiFi cluster is "
                               "one instance, not one per node.",
                "table": {
                    "actions": ["edit", "delete", "clone"],
                    "header": [
                        {"label": "Name", "field": "name"},
                        {"label": "API URL", "field": "api_url"},
                        {"label": "Authentication", "field": "auth_type"},
                        {"label": "Interval", "field": "interval"},
                        {"label": "Index", "field": "index"},
                        {"label": "Status", "field": "disabled"},
                    ],
                    "moreInfo": [
                        {"label": "Name", "field": "name"},
                        {"label": "API URL", "field": "api_url"},
                        {"label": "Authentication", "field": "auth_type"},
                        {"label": "Username", "field": "username"},
                        {"label": "Interval", "field": "interval"},
                        {"label": "Index", "field": "index"},
                        {"label": "Host", "field": "host"},
                        {"label": "Verify TLS", "field": "verify_tls"},
                        {"label": "CA bundle", "field": "ca_bundle"},
                        {"label": "Additional endpoints", "field": "custom_endpoints"},
                        {"label": "Status", "field": "disabled",
                         "mapping": {"true": "Disabled", "false": "Enabled"}},
                    ],
                },
                "services": [
                    {
                        "name": "nifi",
                        "title": "NiFi instance",
                        "subTitle": "Polls the NiFi REST API on each interval.",
                        "entity": entity,
                        "groups": groups,
                    }
                ],
            },
        },
        "options": {
            "restHandlers": [
                {
                    "name": "nifi_test_connection",
                    "endpoint": "nifi_test_connection",
                    "handlerType": "EAI",
                    "registerHandler": {
                        "file": "nifi_rh_test_connection.py",
                        "actions": ["create"],
                    },
                }
            ]
        },
    }


if __name__ == "__main__":
    with open(TARGET, "w") as handle:
        json.dump(build(), handle, indent=4)
        handle.write("\n")
    print("wrote %s" % os.path.normpath(TARGET))
