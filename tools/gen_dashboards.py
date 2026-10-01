#!/usr/bin/env python3
"""Generate the app's Dashboard Studio views.

The views are Dashboard Studio (version 2) XML files whose body is a JSON
definition. Written by hand that JSON is several thousand lines of positions,
ids and repeated option blocks; here each view is a short list of rows and
panels, and this script lays them out.

    python3 tools/gen_dashboards.py          # write the views
    python3 tools/gen_dashboards.py --check  # exit 1 if they drifted

Edit this file, not the XML: a unit test fails if the shipped views differ
from a clean run (tests/unit/test_dashboards.py).

Plan: docs/plans/2026-10-01-rediseno-dashboards.md
"""

import argparse
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIEWS = os.path.join(REPO, "nifi_monitoring", "default", "data", "ui", "views")
APP = "nifi_monitoring"
WIDTH = 1440
GAP = 0

# Status colours, fixed: never used for a series (docs/plans/mockups).
CRITICAL = "#D03B3B"
WARNING = "#FAB219"
GOOD = "#0CA30C"
MUTED = "#9A9890"
SERIES = ["#2A78D6", "#EB6834", "#1BAF7A", "#EDA100"]

BULLETIN = '`index_nifi` sourcetype IN ("nifi:api:bulletin_board", "nifi:reporting:bulletin")'
LEVEL_COLORS = {"ERROR": CRITICAL, "WARNING": WARNING, "WARN": WARNING, "INFO": MUTED}
HEALTH_COLORS = [
    {"match": "✕ Critical", "value": CRITICAL},
    {"match": "! Degraded", "value": "#B07A00"},
    {"match": "○ Stale", "value": MUTED},
    {"match": "○ No data", "value": MUTED},
    {"match": "✓ Healthy", "value": GOOD},
]
# health -> the label a table shows, with its icon, so status is never colour alone
HEALTH_LABEL = ('eval Health = case(health == "critical", "✕ Critical", health == "degraded", "! Degraded", '
                'health == "stale", "○ Stale", health == "no_data", "○ No data", true(), "✓ Healthy")')
HOST_FILTER = '| search host="$host$"'
# seconds -> "13 s", "4 min", "2 h 14 min"
AGO = ('case(isnull(age), "never", age < 120, round(age) . " s ago", age < 7200, round(age / 60) . " min ago", '
       'true(), floor(age / 3600) . " h " . round((age % 3600) / 60) . " min ago")')


# ---------------------------------------------------------------------------
# building blocks
# ---------------------------------------------------------------------------

class View(object):
    """One dashboard: data sources, visualizations, inputs and a grid layout."""

    def __init__(self, name, title, description, inputs=()):
        self.name, self.title, self.description = name, title, description
        self.data_sources, self.visualizations, self.inputs = {}, {}, {}
        self.input_order = []
        self.rows = []          # [(height, [(viz_id, width_fraction)])]
        self.token_defaults = {}  # tokens a click sets, with their value before any click
        for item in inputs:
            self.add_input(*item)

    # -- data ---------------------------------------------------------------

    def search(self, ds_id, query, earliest="$time.earliest$", latest="$time.latest$",
               refresh=None, name=None):
        options = {"query": query.strip(), "queryParameters": {"earliest": earliest, "latest": latest}}
        if refresh:
            options.update({"refresh": refresh, "refreshType": "delay"})
        self.data_sources[ds_id] = {"type": "ds.search", "options": options, "name": name or ds_id}
        return ds_id

    def chain(self, ds_id, base, query, name=None):
        self.data_sources[ds_id] = {"type": "ds.chain",
                                    "options": {"extend": base, "query": query.strip()},
                                    "name": name or ds_id}
        return ds_id

    # -- inputs -------------------------------------------------------------

    def add_input(self, kind, token, title, default, extra=None):
        input_id = "input_" + token
        if kind == "time":
            spec = {"type": "input.timerange", "title": title,
                    "options": {"token": token, "defaultValue": default}}
        elif kind == "dropdown" or kind == "multiselect":
            options = {"token": token, "defaultValue": default, "items": [{"label": "All", "value": "*"}]}
            spec = {"type": "input." + kind, "title": title, "options": options}
            if extra and extra.get("items"):
                options["items"] = extra["items"]
            if extra and extra.get("search"):
                field = extra.get("field", token)
                ds = self.search("ds_input_" + token, extra["search"],
                                 earliest=extra.get("earliest", "-24h@h"), latest="now",
                                 name="Choices for " + title)
                statics = [] if extra.get("no_all") else [["All"], ["*"]]
                options["items"] = ">frame(label, value) | prepend(formattedStatics) | objects()"
                spec["dataSources"] = {"primary": ds}
                spec["context"] = {
                    "formattedConfig": {"number": {"prefix": ""}},
                    "formattedStatics": ">statics | formatByType(formattedConfig)",
                    "statics": statics,
                    "label": '>primary | seriesByName("%s") | renameSeries("label") | formatByType(formattedConfig)' % field,
                    "value": '>primary | seriesByName("%s") | renameSeries("value") | formatByType(formattedConfig)' % field,
                }
                if extra.get("select_first"):
                    options["selectFirstSearchResult"] = True
                    options.pop("defaultValue", None)
        elif kind == "text":
            spec = {"type": "input.text", "title": title, "options": {"token": token, "defaultValue": default}}
        else:
            raise ValueError(kind)
        self.inputs[input_id] = spec
        self.input_order.append(input_id)

    # -- visualizations -----------------------------------------------------

    def viz(self, viz_id, kind, ds, title=None, description=None, options=None, context=None,
            drilldown=None):
        spec = {"type": kind, "options": options or {}}
        if ds:
            spec["dataSources"] = {"primary": ds}
        if title:
            spec["title"] = title
        if description:
            spec["description"] = description
        if context:
            spec["context"] = context
        if drilldown:
            spec["eventHandlers"] = [drilldown]
        self.visualizations[viz_id] = spec
        return viz_id

    def kpi(self, viz_id, ds, title, field, unit=None, ranges=None, under=None, drilldown=None,
            description=None, severity=None, under_field=None):
        """A single value. ranges: [(from, colour)] ascending, applied to the
        value -- for counts only. A threshold comparison is the search's job:
        severity names a field holding ok / warning / critical, computed with
        the threshold that applies to the instance, and colours the value."""
        options = {"majorValue": '> primary | seriesByName("%s") | lastPoint()' % field,
                   "trendDisplay": "off", "sparklineDisplay": "off",
                   "majorFontSize": 34}
        context = {}
        if unit:
            options["unit"] = unit
        if under:
            options["underLabel"] = under
        if under_field:
            options["underLabel"] = '> primary | seriesByName("%s") | lastPoint()' % under_field
        if severity:
            options["majorColor"] = '> primary | seriesByName("%s") | lastPoint() | matchValue(severityColorConfig)' % severity
            context["severityColorConfig"] = [
                {"match": "critical", "value": CRITICAL}, {"match": "warning", "value": WARNING},
                {"match": "ok", "value": GOOD}]
        if ranges:
            config = []
            for i, (start, colour) in enumerate(ranges):
                entry = {"value": colour}
                if start is not None:
                    entry["from"] = start
                if i + 1 < len(ranges):
                    entry["to"] = ranges[i + 1][0]
                config.append(entry)
            options["majorColor"] = "> majorValue | rangeValue(majorColorEditorConfig)"
            context["majorColorEditorConfig"] = config
        return self.viz(viz_id, "splunk.singlevalue", ds, title, description, options, context or None,
                        drilldown)

    def text_kpi(self, viz_id, ds, title, field, description=None):
        """A single value that is a string (a name, a version, "3 / 3")."""
        options = {"majorValue": '> primary | seriesByName("%s") | lastPoint()' % field,
                   "trendDisplay": "off", "sparklineDisplay": "off", "majorFontSize": 22}
        return self.viz(viz_id, "splunk.singlevalue", ds, title, description, options)

    def table(self, viz_id, ds, title=None, description=None, count=10, colors=None, drilldown=None,
              sparklines=(), widths=None):
        options = {"count": count, "showInternalFields": False, "headerVisibility": "fixed",
                   "backgroundColor": "transparent", "tableFormat": {
                       "rowBackgroundColors": "> table | seriesByIndex(0) | noRecolor()",
                       "headerBackgroundColor": "> backgroundColor | setColorChannel(tableHeaderBackgroundColorConfig)",
                       "rowColors": "> rowBackgroundColors | maxContrast(tableRowColorMaxContrast)",
                       "headerColor": "> headerBackgroundColor | maxContrast(tableRowColorMaxContrast)"}}
        context = {"tableHeaderBackgroundColorConfig": {"channel": "rgb", "value": "#E1E0D9"},
                   "tableRowColorMaxContrast": {"maximum": "#0B0B0B", "minimum": "#FFFFFF"}}
        column_format = {}
        for column, matches in (colors or {}).items():
            key = "%sRowColorsEditorConfig" % column.replace(" ", "_").replace("·", "")
            column_format[column] = {"rowColors": '> table | seriesByName("%s") | matchValue(%s)' % (column, key)}
            context[key] = matches
        for column in sparklines:
            key = "%sSparklineConfig" % column.replace(" ", "_")
            column_format[column] = {"data": '> table | seriesByName("%s") | formatByType(%s)' % (column, key)}
            context[key] = {"sparkline": {"sparklineType": "line", "sparklineColors": SERIES[0]}}
        for column, width in (widths or {}).items():
            column_format.setdefault(column, {})["width"] = width
        if column_format:
            options["columnFormat"] = column_format
        return self.viz(viz_id, "splunk.table", ds, title, description, options, context, drilldown)

    def chart(self, viz_id, kind, ds, title, description=None, stacked=False, colors=None,
              ymax=None, dashed=(), legend="bottom", unit=None, drilldown=None):
        options = {"legendDisplay": legend, "xAxisTitleVisibility": "hide", "yAxisTitleVisibility": "hide",
                   "showSplitSeries": False, "showRoundedY2AxisLabels": False,
                   "seriesColors": SERIES}
        if stacked:
            options["stackMode"] = "stacked"
        if colors:
            options["seriesColorsByField"] = colors
        if ymax is not None:
            options["yAxisMax"] = ymax
            options["yAxisMin"] = 0
        if dashed:
            options["lineDashStylesByField"] = {f: "dash" for f in dashed}
        if unit:
            options["yAxisTitleText"] = unit
            options["yAxisTitleVisibility"] = "show"
        if kind == "splunk.line":
            options["nullValueDisplay"] = "connect"
        return self.viz(viz_id, kind, ds, title, description, options, drilldown=drilldown)

    def markdown(self, viz_id, text):
        return self.viz(viz_id, "splunk.markdown", None, options={"markdown": text, "fontSize": "default"})

    # -- layout -------------------------------------------------------------

    def row(self, height, *cells):
        """cells: viz ids, or (viz id, relative width)."""
        cells = [c if isinstance(c, tuple) else (c, 1) for c in cells]
        self.rows.append((height, cells))

    def definition(self):
        structure, y = [], 0
        for height, cells in self.rows:
            total = float(sum(w for _, w in cells))
            x = 0
            for i, (viz_id, w) in enumerate(cells):
                width = WIDTH - x if i == len(cells) - 1 else int(round(WIDTH * w / total))
                structure.append({"item": viz_id, "type": "block",
                                  "position": {"x": x, "y": y, "w": width, "h": height}})
                x += width
            y += height
        defaults = {"dataSources": {"ds.search": {"options": {"queryParameters": {
            "earliest": "$time.earliest$", "latest": "$time.latest$"}}}}}
        if self.token_defaults:
            defaults["tokens"] = {"default": {k: {"value": v} for k, v in self.token_defaults.items()}}
        return {
            "title": self.title,
            "description": self.description,
            "inputs": self.inputs,
            "defaults": defaults,
            "visualizations": self.visualizations,
            "dataSources": self.data_sources,
            "layout": {"type": "grid", "options": {"width": WIDTH, "height": max(y, 400)},
                       "structure": structure, "globalInputs": self.input_order},
        }

    def xml(self):
        body = json.dumps(self.definition(), indent=4, ensure_ascii=False, sort_keys=True)
        assert "]]>" not in body
        return ('<dashboard version="2" theme="light" hideEdit="false">\n'
                "  <label>%s</label>\n"
                "  <description>%s</description>\n"
                "  <definition><![CDATA[\n%s\n]]></definition>\n"
                '  <meta type="hiddenElements"><![CDATA[\n{"hideEdit": false, "hideOpenInSearch": false, '
                '"hideExport": false}\n]]></meta>\n'
                "</dashboard>\n") % (self.title, self.description, body)


def link(view, **tokens):
    """A drilldown to another view, passing tokens through the URL. Every view
    has a time range, and the one the user is looking at goes along."""
    tokens.setdefault("time.earliest", "$time.earliest$")
    tokens.setdefault("time.latest", "$time.latest$")
    query = "&".join("form.%s=%s" % (k, v) for k, v in tokens.items())
    return {"type": "drilldown.customUrl",
            "options": {"url": "/app/%s/%s%s" % (APP, view, "?" + query if query else ""), "newTab": False}}


def set_token(token, field):
    return {"type": "drilldown.setToken",
            "options": {"tokens": [{"token": token, "key": "row.%s.value" % field}]}}


HOST_CHOICES = "| `nifi_fleet` | sort health_rank host | fields host"


# ---------------------------------------------------------------------------
# views
# ---------------------------------------------------------------------------

def overview():
    v = View("nifi_overview", "Overview", "Is the fleet healthy right now?", inputs=[
        ("time", "time", "Time range", "-4h@m,now"),
        ("dropdown", "cluster", "Cluster", "*",
         {"search": "| inputlookup instance | stats count by cluster | fields cluster", "field": "cluster"}),
    ])
    fleet = v.search("ds_fleet", '| `nifi_fleet` | search cluster="$cluster$"',
                     earliest="-24h", latest="now", refresh="1m", name="Fleet")
    v.kpi("viz_healthy", v.chain("ds_k_healthy", fleet,
          '| stats count(eval(health=="ok")) as ok, count as total | eval value = ok . " / " . total'),
          "Healthy instances", "value",
          description="Healthy out of every instance in the inventory, heard from or not")
    v.kpi("viz_bulletins", v.chain("ds_k_bulletins", fleet, "| stats sum(bulletin_errors) as value | fillnull value=0 value"),
          "ERROR bulletins · 15 min", "value", ranges=[(None, GOOD), (1, CRITICAL)],
          drilldown=link("nifi_bulletins", level="ERROR"))
    v.kpi("viz_heap", v.chain("ds_k_heap", fleet,
          "| where isnotnull(heap_pct) | sort - heap_pct | head 1 | rename heap_pct as value | fields value heap_severity host"),
          "Worst heap", "value", unit="%", severity="heap_severity", under_field="host",
          description="Highest heap use; coloured by that instance's threshold")
    v.kpi("viz_repo", v.chain("ds_k_repo", fleet,
          "| where isnotnull(worst_repo_pct) | sort - worst_repo_pct | head 1 "
          "| eval where = host . \" · \" . worst_repo | rename worst_repo_pct as value | fields value repo_severity where"),
          "Worst repository", "value", unit="%", severity="repo_severity", under_field="where",
          description="Fullest repository of any instance; coloured by that instance's threshold")
    v.kpi("viz_queued", v.chain("ds_k_queued", fleet, "| stats sum(flowfiles_queued) as value | fillnull value=0 value"),
          "FlowFiles queued", "value", description="Across every instance")
    v.kpi("viz_invalid", v.chain("ds_k_invalid", fleet, "| stats sum(invalid) as value | fillnull value=0 value"),
          "Invalid components", "value", ranges=[(None, GOOD), (1, WARNING)])
    v.row(130, "viz_healthy", "viz_bulletins", "viz_heap", "viz_repo", "viz_queued", "viz_invalid")

    table = v.chain("ds_t_instances", fleet, r'''
| sort health_rank host
| %s
| eval "Last data" = %s,
       Components = if(isnull(running), "—", "▶ " . running . "  ■ " . stopped . "  ⚠ " . invalid . "  ⏻ " . disabled),
       Queued = if(isnull(flowfiles_queued), "—", flowfiles_queued . " · " . round(bytes_queued / 1048576, 1) . " MB"),
       "Heap %%" = heap_pct, "Worst repository" = if(isnull(worst_repo_pct), "—", worst_repo_pct . "%% · " . worst_repo)
| table Health health_reason host cluster nifi_version "Last data" Components Queued "Heap %%" "Worst repository" bulletin_errors
| rename health_reason as Reason, host as Instance, cluster as Cluster, nifi_version as NiFi, bulletin_errors as "ERROR · 15m"
''' % (HEALTH_LABEL, AGO))
    v.table("viz_instances", table, "Instances",
            "Sorted by severity. Components: ▶ running · ■ stopped · ⚠ invalid · ⏻ disabled. Click a row to open it.",
            count=20, colors={"Health": HEALTH_COLORS},
            drilldown=link("nifi_instance", host="$row.Instance.value$"))
    v.row(330, "viz_instances")

    v.chart("viz_bulletins_time", "splunk.column", v.search("ds_bulletins_time", r'''
| tstats count from datamodel=NIFI.Bulletins where host=* by _time Bulletins.bulletinLevel span=10m
| rename Bulletins.bulletinLevel as level
| lookup instance host OUTPUT cluster | fillnull value="—" cluster | search cluster="$cluster$"
| timechart span=10m sum(count) by level
'''), "Bulletins by level", "All instances · 10-minute buckets", stacked=True, colors=LEVEL_COLORS,
            drilldown=link("nifi_bulletins"))
    v.chart("viz_queue_time", "splunk.line", v.search("ds_queue_time", r'''
| tstats latest(Flow_Status.controllerStatus.flowFilesQueued) as queued from datamodel=NIFI.Flow_Status by _time host span=5m
| lookup instance host OUTPUT cluster | fillnull value="—" cluster | search cluster="$cluster$"
| timechart span=5m max(queued) by host limit=4 useother=true
'''), "FlowFiles queued by instance", "Top 4 by queue; the rest fold into OTHER")
    v.row(300, "viz_bulletins_time", "viz_queue_time")
    v.markdown("viz_footer", "Developed by [Kudaw](https://www.kudaw.com)")
    v.row(40, "viz_footer")
    return v


def instance():
    v = View("nifi_instance", "Instance", "What is happening on this instance?", inputs=[
        ("dropdown", "host", "Instance", None,
         {"search": HOST_CHOICES, "field": "host", "no_all": True, "select_first": True, "earliest": "-24h"}),
        ("time", "time", "Time range", "-4h@m,now"),
    ])
    fleet = v.search("ds_fleet", '| `nifi_fleet` %s' % HOST_FILTER, earliest="-24h", latest="now",
                     refresh="1m", name="This instance")
    v.table("viz_header", v.chain("ds_header", fleet, r'''
| %s
| eval "Last data" = %s . " · interval " . interval . " s"
| table Health health_reason cluster nifi_version java_version uptime "Last data"
| rename health_reason as Reason, cluster as Cluster, nifi_version as NiFi, java_version as Java, uptime as Uptime
''' % (HEALTH_LABEL, AGO)), colors={"Health": HEALTH_COLORS}, count=1)
    v.row(110, "viz_header")

    v.markdown("viz_now", "### Now")
    v.row(40, "viz_now")
    v.kpi("viz_threads", v.chain("ds_k_threads", fleet, "| fields threads"), "Active threads", "threads")
    v.kpi("viz_queued", v.chain("ds_k_queued", fleet, "| fields flowfiles_queued"), "FlowFiles queued",
          "flowfiles_queued")
    v.kpi("viz_queued_mb", v.chain("ds_k_queued_mb", fleet, "| eval mb = round(bytes_queued / 1048576, 1) | fields mb"),
          "Bytes queued", "mb", unit="MB")
    v.text_kpi("viz_components", v.chain("ds_k_components", fleet,
               '| eval value = "▶ " . running . "  ■ " . stopped . "  ⚠ " . invalid . "  ⏻ " . disabled | fields value'),
               "Components", "value", description="running · stopped · invalid · disabled")
    v.text_kpi("viz_versioned", v.chain("ds_k_versioned", fleet,
               '| eval value = up_to_date . " · " . locally_modified . " · " . stale_groups . " · " . sync_failure | fields value'),
               "Versioned process groups", "value", description="up to date · modified · stale · failing to sync")
    v.kpi("viz_errors", v.chain("ds_k_errors", fleet, "| fields bulletin_errors"), "ERROR bulletins · 15 min",
          "bulletin_errors", ranges=[(None, GOOD), (1, CRITICAL)],
          drilldown=link("nifi_bulletins", host="$host$", level="ERROR"))
    v.row(130, "viz_threads", "viz_queued", "viz_queued_mb", ("viz_components", 1.4), ("viz_versioned", 1.4), "viz_errors")

    v.markdown("viz_jvm", "### JVM and system")
    v.row(40, "viz_jvm")
    diag = v.search("ds_diag", r'''
`index_nifi` sourcetype="nifi:api:system_diagnostics" host="$host$"
| eval heap = round('systemDiagnostics.aggregateSnapshot.usedHeapBytes' * 100 / 'systemDiagnostics.aggregateSnapshot.maxHeapBytes', 1),
       total = 'systemDiagnostics.aggregateSnapshot.totalThreads', daemon = 'systemDiagnostics.aggregateSnapshot.daemonThreads',
       load = 'systemDiagnostics.aggregateSnapshot.processorLoadAverage', cores = 'systemDiagnostics.aggregateSnapshot.availableProcessors'
| fields _time heap total daemon load cores
''', name="System diagnostics")
    v.chart("viz_heap", "splunk.line", v.chain("ds_heap", diag,
            '| timechart span=5m max(heap) as "Heap used %" | eval host = "$host$" | `nifi_instance_thresholds` '
            '| eval Threshold = heap_warn | fields _time "Heap used %" Threshold'),
            "Heap used", "% of max heap · dashed line: this instance's heap threshold", ymax=100, dashed=["Threshold"],
            colors={"Heap used %": SERIES[0], "Threshold": "#52514E"})
    v.chart("viz_threads_time", "splunk.line", v.chain("ds_threads", diag,
            "| timechart span=5m max(total) as Total, max(daemon) as Daemon"),
            "JVM threads", "Total and daemon")
    v.row(280, "viz_heap", "viz_threads_time")
    v.chart("viz_load", "splunk.line", v.chain("ds_load", diag,
            '| timechart span=5m max(load) as "Load average", max(cores) as Cores'),
            "Load average", "1-minute load · dashed line: available cores", dashed=["Cores"],
            colors={"Load average": SERIES[0], "Cores": "#52514E"})
    v.chart("viz_gc", "splunk.line", v.search("ds_gc", r'''
`index_nifi` sourcetype="nifi:api:system_diagnostics" host="$host$"
| eval gc = mvzip('systemDiagnostics.aggregateSnapshot.garbageCollection{}.name', 'systemDiagnostics.aggregateSnapshot.garbageCollection{}.collectionMillis', "|")
| fields _time gc | mvexpand gc
| eval collector = mvindex(split(gc, "|"), 0), ms = tonumber(mvindex(split(gc, "|"), 1))
| sort 0 _time | streamstats current=f last(ms) as previous by collector
| eval spent = if(ms >= previous, ms - previous, null())
| timechart span=5m sum(spent) by collector
'''), "GC time per collector", "Milliseconds spent per 5 minutes (delta, not the running total)")
    v.row(280, "viz_load", "viz_gc")

    v.markdown("viz_storage", "### Storage")
    v.row(40, "viz_storage")
    repos = v.search("ds_repos", r'''
`index_nifi` sourcetype="nifi:api:system_diagnostics" host="$host$"
| `nifi_repositories` | fields _time repository | mvexpand repository
| eval _r = split(repository, "|"), type = mvindex(_r, 0), identifier = mvindex(_r, 1),
       used = tonumber(mvindex(_r, 2)), total = tonumber(mvindex(_r, 3)), pct = round(used * 100 / total, 1),
       repo = type . " · " . identifier
| fields _time repo type identifier used total pct
''', name="Repositories")
    v.table("viz_repos", v.chain("ds_repos_now", repos, r'''
| dedup repo
| eval "Used GB" = round(used / 1073741824, 1), "Total GB" = round(total / 1073741824, 1)
| sort type identifier
| table type identifier "Used GB" "Total GB" pct
| rename type as Repository, identifier as Identifier, pct as "Used %"
'''), "Repositories", "Latest value, one row per repository")
    v.chart("viz_repo_time", "splunk.line", v.chain("ds_repo_time", repos,
            '| timechart span=5m max(pct) by repo | eval host = "$host$" | `nifi_instance_thresholds` '
            '| eval Threshold = repo_warn | fields - host heap_* repo_threshold* repo_warn repo_crit backpressure_* bulletin_*'),
            "Repository usage", "% used · dashed line: this instance's repository threshold", ymax=100, dashed=["Threshold"])
    v.row(260, ("viz_repos", 5), ("viz_repo_time", 7))

    v.markdown("viz_tp", "### Throughput\n"
               "Root process group, per 5 minutes. On the pull path it needs *Flow metrics* "
               "(`endpoint_flow_metrics`) enabled on this instance's input in the Nifi Monitoring TA; "
               "on the push path it comes from the Reporting Task.")
    v.row(70, "viz_tp")
    tp = v.search("ds_tp", r'''
| tstats latest(Throughput.bytes_in) as bytes_in, latest(Throughput.bytes_out) as bytes_out,
         latest(Throughput.bytes_written) as bytes_written,
         latest(Throughput.flowfiles_in) as flowfiles_in, latest(Throughput.flowfiles_out) as flowfiles_out
  from datamodel=NIFI.Throughput where host="$host$" by _time span=5m
''', name="Throughput")
    v.chart("viz_bytes", "splunk.line", v.chain("ds_bytes", tp,
            '| eval Received = round(bytes_in / 1048576, 1), Sent = round(bytes_out / 1048576, 1), Written = round(bytes_written / 1048576, 1) | fields _time Received Sent Written'),
            "Data in, out and processed", "MB per 5 minutes · received from and sent to outside NiFi, and written to the content repository")
    v.chart("viz_flowfiles", "splunk.line", v.chain("ds_flowfiles", tp,
            '| rename flowfiles_in as Received, flowfiles_out as Sent | fields _time Received Sent'),
            "FlowFiles received and sent", "Per 5 minutes, from and to outside NiFi")
    v.row(260, "viz_bytes", "viz_flowfiles")

    v.table("viz_recent", v.search("ds_recent", r'''
%s host="$host$"
| head 10
| eval Time = strftime(_time, "%%Y-%%m-%%d %%H:%%M:%%S")
| table Time bulletinLevel bulletinSourceName bulletinMessage
| rename bulletinLevel as Level, bulletinSourceName as Component, bulletinMessage as Message
''' % BULLETIN), "Recent bulletins", "Latest 10 · click a row to open Bulletins", widths={"Message": 900},
            colors={"Level": [{"match": k, "value": c} for k, c in LEVEL_COLORS.items()]},
            drilldown=link("nifi_bulletins", host="$host$"))
    v.row(330, "viz_recent")
    return v


def components():
    v = View("nifi_components", "Components",
             "Which processor, group or connection is the bottleneck?", inputs=[
        ("dropdown", "host", "Instance", None,
         {"search": HOST_CHOICES, "field": "host", "no_all": True, "select_first": True, "earliest": "-24h"}),
        ("dropdown", "kind", "Component type", "processor",
         {"items": [{"label": "Processors", "value": "processor"},
                    {"label": "Process groups", "value": "process_group"}]}),
        ("dropdown", "metric", "Metric", "taskMillis",
         {"search": '| inputlookup nifi_status_metrics | search component_type="$kind$" OR component_type="both" '
                    '| eval label = label . " (" . unit . ")" | fields field label',
          "field": "field", "no_all": True}),
        ("dropdown", "operation", "Operation", "sum",
         {"items": [{"label": "Sum", "value": "sum"}, {"label": "Average", "value": "avg"},
                    {"label": "Max", "value": "max"}]}),
        ("time", "time", "Time range", "-4h@m,now"),
    ])
    # the metric dropdown labels its choices with the label column
    v.inputs["input_metric"]["context"]["label"] = '>primary | seriesByName("label") | renameSeries("label") | formatByType(formattedConfig)'

    conn = v.search("ds_connections", r'''
`index_nifi` sourcetype="nifi:api:flow_metrics" host="$host$" component_type="Connection"
  metric_name IN ("nifi_percent_used_count", "nifi_percent_used_bytes", "nifi_time_to_count_backpressure_prediction", "nifi_time_to_bytes_backpressure_prediction")
| stats latest(metric_value) as value, latest(source_name) as source, latest(destination_name) as destination by component_id metric_name
| eval metric = case(metric_name == "nifi_percent_used_count", "objects", metric_name == "nifi_percent_used_bytes", "size", metric_name == "nifi_time_to_count_backpressure_prediction", "eta_count", true(), "eta_bytes")
| eval {metric} = value
| stats values(source) as source, values(destination) as destination, max(objects) as objects, max(size) as size, min(eta_count) as eta_count, min(eta_bytes) as eta_bytes by component_id
| eval eta = min(if(eta_count > 0, eta_count, null()), if(eta_bytes > 0, eta_bytes, null()))
''', name="Connections")
    v.kpi("viz_over", v.chain("ds_k_over", conn,
          '| eval host = "$host$" | `nifi_instance_thresholds` '
          "| where objects >= backpressure_warn OR size >= backpressure_warn | stats count as value"),
          "Connections over backpressure threshold", "value", ranges=[(None, GOOD), (1, WARNING)],
          description="% of the object or size limit ≥ this instance's backpressure threshold · needs flow metrics")
    v.kpi("viz_eta", v.chain("ds_k_eta", conn,
          "| where eta > 0 AND eta < `nifi_backpressure_horizon` * 1000 | stats count as value"),
          "Reaching backpressure soon", "value", ranges=[(None, GOOD), (1, CRITICAL)],
          description="NiFi's own prediction, within nifi_backpressure_horizon (1 h by default)")
    v.kpi("viz_tracked", v.search("ds_tracked", r'''
| tstats dc(Component_Status.component_key) as value from datamodel=NIFI.Component_Status where host="$host$"
'''), "Components with history", "value",
          description="Only the ids configured on the TA input (or the push flow's processors_list)")
    v.row(130, "viz_over", "viz_eta", "viz_tracked")

    status = v.search("ds_status", r'''
| tstats $operation$(Component_Status.$metric$) as v from datamodel=NIFI.Component_Status
  where host="$host$" Component_Status.component_kind="$kind$"
  by _time Component_Status.component_label span=5m
| rename Component_Status.component_label as component
''', name="Component status")
    v.table("viz_top", v.chain("ds_top", status, r'''
| stats $operation$(v) as value, sparkline($operation$(v), 5m) as trend by component
| sort - value | head 10
| eval value = round(value, 1)
| rename component as Component, value as "$metric$ ($operation$)", trend as Trend
'''), "Top 10 by the selected metric", "Click a row to plot it below", count=10, sparklines=["Trend"],
            drilldown=set_token("component", "Component"))
    v.table("viz_conn", v.chain("ds_conn_table", conn, r'''
| eval Connection = source . " → " . destination, "Objects %" = round(objects, 0), "Size %" = round(size, 0),
       "To backpressure" = if(isnull(eta) OR eta <= 0, "—", tostring(round(eta / 1000), "duration"))
| sort - "Objects %"
| table Connection "Objects %" "Size %" "To backpressure"
'''), "Busiest connections",
            "Latest · % of the backpressure limit · needs flow metrics (endpoint_flow_metrics)", count=10)
    v.row(380, "viz_top", "viz_conn")

    v.token_defaults["component"] = "*"
    v.chart("viz_series", "splunk.line", v.chain("ds_series", status,
            '| search component="$component$" | timechart span=5m max(v) by component limit=5 useother=false'),
            "Selected component", "$metric$ per 5 minutes · all components until a row above is clicked")
    v.row(300, "viz_series")
    return v


def bulletins():
    v = View("nifi_bulletins", "Bulletins", "What errors is NiFi reporting?", inputs=[
        ("time", "time", "Time range", "-24h@h,now"),
        ("dropdown", "host", "Instance", "*",
         {"search": "| tstats count from datamodel=NIFI.Bulletins by host | fields host", "field": "host"}),
        ("dropdown", "level", "Level", "*",
         {"items": [{"label": "All", "value": "*"}, {"label": "ERROR", "value": "ERROR"},
                    {"label": "WARNING", "value": "WARNING"}, {"label": "INFO", "value": "INFO"}]}),
        ("dropdown", "category", "Category", "*",
         {"search": "| tstats count from datamodel=NIFI.Bulletins by Bulletins.bulletinCategory "
                    "| rename Bulletins.bulletinCategory as category | fields category", "field": "category"}),
        ("text", "source", "Component", "*"),
    ])
    base = v.search("ds_base", r'''
| tstats count from datamodel=NIFI.Bulletins
  where host="$host$" Bulletins.bulletinLevel="$level$" Bulletins.bulletinCategory="$category$" Bulletins.bulletinSourceName="$source$"
  by _time host Bulletins.bulletinLevel Bulletins.bulletinSourceName Bulletins.bulletinSourceId span=1h
| rename Bulletins.* as *
''', name="Bulletins")
    v.kpi("viz_total", v.chain("ds_k_total", base, "| stats sum(count) as value | fillnull value=0 value"), "Bulletins", "value")
    v.kpi("viz_errors", v.chain("ds_k_errors", base, '| stats sum(eval(if(bulletinLevel=="ERROR", count, 0))) as value | fillnull value=0 value'),
          "ERROR", "value", ranges=[(None, GOOD), (1, CRITICAL)])
    v.kpi("viz_warnings", v.chain("ds_k_warnings", base, '| stats sum(eval(if(bulletinLevel=="WARNING", count, 0))) as value | fillnull value=0 value'),
          "WARNING", "value", ranges=[(None, GOOD), (1, WARNING)])
    v.kpi("viz_affected", v.chain("ds_k_affected", base, "| stats dc(bulletinSourceId) as value | fillnull value=0 value"),
          "Components affected", "value")
    v.row(130, "viz_total", "viz_errors", "viz_warnings", "viz_affected")
    v.chart("viz_time", "splunk.column", v.chain("ds_time", base,
            "| timechart span=1h sum(count) by bulletinLevel"),
            "Bulletins over time", "Hourly, by level", stacked=True, colors=LEVEL_COLORS)
    v.table("viz_top", v.chain("ds_top", base, r'''
| eval e = if(bulletinLevel == "ERROR", count, 0), w = if(bulletinLevel == "WARNING", count, 0)
| stats sum(e) as ERROR, sum(w) as WARNING by bulletinSourceName
| sort - ERROR - WARNING | head 8 | rename bulletinSourceName as Component
'''), "Components with most bulletins", count=8, drilldown=set_token("source", "Component"))
    v.row(300, ("viz_time", 8), ("viz_top", 4))
    v.table("viz_detail", v.search("ds_detail", r'''
%s host="$host$" bulletinLevel="$level$" bulletinCategory="$category$" bulletinSourceName="$source$"
| eval Group = coalesce(bulletinGroupPath, bulletinGroupName, bulletinGroupId), Time = strftime(_time, "%%Y-%%m-%%d %%H:%%M:%%S")
| table Time host bulletinLevel bulletinCategory bulletinSourceName Group bulletinMessage
| rename host as Instance, bulletinLevel as Level, bulletinCategory as Category, bulletinSourceName as Component, bulletinMessage as Message
''' % BULLETIN), "Bulletin details", "Whole message · the group name only comes with the push path; pull shows its id",
            count=15, colors={"Level": [{"match": k, "value": c} for k, c in LEVEL_COLORS.items()]},
            widths={"Message": 700})
    v.row(520, "viz_detail")
    return v


def logs():
    v = View("nifi_logs", "Logs", "Application log, deprecations and API requests", inputs=[
        ("time", "time", "Time range", "-60m@m,now"),
        ("dropdown", "host", "Instance", "*",
         {"search": "| tstats count where `index_nifi` sourcetype=nifi:log:* by host | fields host", "field": "host"}),
        ("dropdown", "level", "Severity", "*",
         {"items": [{"label": "All", "value": "*"}, {"label": "ERROR", "value": "ERROR"},
                    {"label": "WARN", "value": "WARN"}, {"label": "INFO", "value": "INFO"}]}),
        ("text", "search", "Search", "*"),
    ])
    v.markdown("viz_app", "### Application")
    v.row(40, "viz_app")
    v.chart("viz_levels", "splunk.column", v.search("ds_levels", r'''
| tstats count from datamodel=NIFI.Logs where host="$host$" Logs.level="$level$" by _time Logs.level span=5m
| rename Logs.level as level | timechart span=5m sum(count) by level
'''), "Events by level", "Structured filters only; the search box applies to the events", stacked=True,
            colors=LEVEL_COLORS)
    v.table("viz_events", v.search("ds_events", r'''
`index_nifi` sourcetype="nifi:log:app" host="$host$" level="$level$" $search$
| head 50 | eval Time = strftime(_time, "%Y-%m-%d %H:%M:%S") | table Time host level _raw | rename host as Instance, level as Level, _raw as Event
'''), "Events", "nifi-app.log, newest first, matching the search", count=8, widths={"Event": 650},
            colors={"Level": [{"match": k, "value": c} for k, c in LEVEL_COLORS.items()]})
    v.row(340, ("viz_levels", 5), ("viz_events", 7))

    v.markdown("viz_dep", "### Deprecations\nWhat this NiFi uses that a later version removes: "
               "the list to clear before moving to NiFi 2.x. Needs the nifi-deprecation.log monitor enabled.")
    v.row(70, "viz_dep")
    v.table("viz_deprecations", v.search("ds_deprecations", r'''
`index_nifi` sourcetype="nifi:log:deprecation" host="$host$"
| rex "\]\s+(?<logger>\S+)\s+(?<message>.+)$"
| eval message = substr(message, 1, 240)
| stats count as Occurrences, latest(_time) as last by host logger message
| eval "Last seen" = strftime(last, "%Y-%m-%d %H:%M") | sort - Occurrences
| table host logger message Occurrences "Last seen"
| rename host as Instance, logger as Logger, message as Message
''', earliest="-7d@d", latest="now"), "Deprecated usage · last 7 days", count=10)
    v.row(300, "viz_deprecations")

    v.markdown("viz_req", "### API requests\nFrom nifi-request.log: who calls NiFi's API and what fails.")
    v.row(70, "viz_req")
    v.chart("viz_req_class", "splunk.column", v.search("ds_req_class", r'''
| tstats count from datamodel=NIFI.Request_Log where host="$host$" by _time Request_Log.status span=5m
| eval class = substr('Request_Log.status', 1, 1) . "xx"
| timechart span=5m sum(count) by class
'''), "Requests by status class", "5-minute buckets", stacked=True,
            colors={"2xx": SERIES[0], "3xx": SERIES[2], "4xx": WARNING, "5xx": CRITICAL})
    v.table("viz_req_top", v.search("ds_req_top", r'''
| tstats count from datamodel=NIFI.Request_Log where host="$host$" Request_Log.status>=400
  by Request_Log.user Request_Log.uri_path Request_Log.status
| rename Request_Log.* as * | sort - count | head 10
| rename user as User, uri_path as URI, status as Status, count as Count
'''), "Top failing requests", "4xx and 5xx", count=10)
    v.row(300, "viz_req_class", "viz_req_top")
    return v


def cluster():
    v = View("nifi_cluster", "Cluster", "Is the cluster whole?", inputs=[
        ("dropdown", "host", "Cluster", None,
         {"search": "| tstats count from datamodel=NIFI.Cluster_Nodes by host | fields host",
          "field": "host", "no_all": True, "select_first": True, "earliest": "-24h"}),
        ("time", "time", "Time range", "-4h@m,now"),
    ])
    v.markdown("viz_note", "A standalone NiFi has no cluster to show: this view fills in when the TA polls "
               "a clustered NiFi, which it detects by itself.")
    v.row(50, "viz_note")
    nodes = v.search("ds_nodes", r'''
| tstats latest(_time) as last_seen, latest(Cluster_Nodes.status) as status, values(Cluster_Nodes.roles) as roles,
         latest(Cluster_Nodes.activeThreadCount) as threads, latest(Cluster_Nodes.flowFilesQueued) as queued,
         latest(Cluster_Nodes.heartbeat) as heartbeat,
         latest(Cluster_Nodes.clusterConnectedNodeCount) as connected, latest(Cluster_Nodes.clusterNodeCount) as total
  from datamodel=NIFI.Cluster_Nodes where host="$host$" earliest=-15m latest=now by Cluster_Nodes.node
| rename Cluster_Nodes.node as node
| append [| tstats latest(Node_Diagnostics.systemDiagnostics.aggregateSnapshot.usedHeapBytes) as used,
                  latest(Node_Diagnostics.systemDiagnostics.aggregateSnapshot.maxHeapBytes) as max
           from datamodel=NIFI.Node_Diagnostics where host="$host$" earliest=-15m latest=now by Node_Diagnostics.node
          | rename Node_Diagnostics.node as node | eval heap = round(used * 100 / max, 1) | fields node heap]
| stats values(*) as * by node
''', earliest="-15m", latest="now", refresh="1m", name="Nodes")
    v.kpi("viz_connected", v.chain("ds_k_connected", nodes,
          '| stats max(connected) as c, max(total) as t | eval value = c . " / " . t'),
          "Connected nodes", "value")
    v.text_kpi("viz_primary", v.chain("ds_k_primary", nodes,
               '| search roles="Primary Node" | stats values(node) as value'), "Primary node", "value")
    v.text_kpi("viz_coordinator", v.chain("ds_k_coordinator", nodes,
               '| search roles="Cluster Coordinator" | stats values(node) as value'), "Cluster coordinator", "value")
    v.row(130, "viz_connected", "viz_primary", "viz_coordinator")
    v.table("viz_nodes", v.chain("ds_nodes_table", nodes, r'''
| eval Status = if(status == "CONNECTED", "✓ " . status, "✕ " . status), Roles = mvjoin(roles, ", ")
| table node Status Roles heartbeat threads queued heap
| rename node as Node, heartbeat as "Last heartbeat", threads as "Active threads", queued as Queued, heap as "Heap %"
'''), "Nodes", colors={"Status": [{"match": "✓ CONNECTED", "value": GOOD}]}, count=10)
    v.row(240, "viz_nodes")
    v.chart("viz_heap", "splunk.line", v.search("ds_heap", r'''
| tstats latest(Node_Diagnostics.systemDiagnostics.aggregateSnapshot.usedHeapBytes) as used,
         latest(Node_Diagnostics.systemDiagnostics.aggregateSnapshot.maxHeapBytes) as max
  from datamodel=NIFI.Node_Diagnostics where host="$host$" by _time Node_Diagnostics.node span=5m
| eval heap = round(used * 100 / max, 1)
| timechart span=5m max(heap) by Node_Diagnostics.node
'''), "Heap used by node", "% of max heap — the aggregate hides the node that runs out", ymax=100)
    v.chart("viz_queue", "splunk.line", v.search("ds_queue", r'''
| tstats latest(Cluster_Nodes.flowFilesQueued) as queued from datamodel=NIFI.Cluster_Nodes
  where host="$host$" by _time Cluster_Nodes.node span=5m
| timechart span=5m max(queued) by Cluster_Nodes.node
'''), "FlowFiles queued by node", "Per 5 minutes")
    v.row(280, "viz_heap", "viz_queue")
    return v


def alerts():
    v = View("nifi_alerts", "Alerts", "What this app can alert on, and what fired", inputs=[
        ("time", "time", "Time range", "-24h@h,now"),
    ])
    shipped = v.search("ds_shipped", r'''
| rest splunk_server=local count=0 /servicesNS/-/nifi_monitoring/saved/searches
| search eai:acl.app="nifi_monitoring" title="NiFi - *"
| eval State = if(disabled == 1 OR disabled == "1", "○ Disabled", "✓ Enabled")
| table title State description cron_schedule
| rename title as Alert, description as Condition, cron_schedule as Schedule
''', earliest="-1m", latest="now", name="Alerts shipped with the app")
    v.kpi("viz_enabled", v.chain("ds_k_enabled", shipped,
          '| stats count(eval(State=="✓ Enabled")) as e, count as t | eval value = e . " / " . t'),
          "Alerts enabled", "value", description="They ship disabled; Settings › Searches, reports, and alerts to enable")
    fired = v.search("ds_fired", r'''
index=_audit action=alert_fired ss_app=nifi_monitoring
| eval Time = strftime(_time, "%Y-%m-%d %H:%M:%S")
| table Time ss_name severity
| rename ss_name as Alert, severity as Severity
''', name="Fired")
    v.kpi("viz_fired", v.chain("ds_k_fired", fired, "| stats count as value"), "Fired in range", "value",
          ranges=[(None, GOOD), (1, CRITICAL)])
    v.markdown("viz_manage", "**Manage** them in *Settings › Searches, reports, and alerts*, app "
               "*nifi_monitoring*: enable, change the recipients, throttle. Thresholds are the "
               "`nifi_threshold_*` macros, the same the panels use.")
    v.row(130, "viz_enabled", "viz_fired", ("viz_manage", 2))
    v.table("viz_shipped", shipped, "Alerts shipped with the app", count=10, widths={"Condition": 650},
            colors={"State": [{"match": "✓ Enabled", "value": GOOD}, {"match": "○ Disabled", "value": MUTED}]})
    v.row(560, "viz_shipped")
    v.table("viz_fired_table", fired, "Fired", count=10)
    v.row(320, "viz_fired_table")
    return v


def collection():
    v = View("nifi_collection_health", "Collection Health", "Is data collection working?", inputs=[
        ("time", "time", "Time range", "-24h@h,now"),
    ])
    v.kpi("viz_events", v.search("ds_events", r'''
| tstats count where `index_nifi` sourcetype=nifi:* | rename count as value
'''), "Events the app can see", "value", ranges=[(None, CRITICAL), (1, GOOD)],
          description="Through the index_nifi macro; zero means the macro points at the wrong index")
    fleet = v.search("ds_fleet", "| `nifi_fleet`", earliest="-24h", latest="now", name="Fleet")
    v.kpi("viz_behind", v.chain("ds_k_behind", fleet,
          '| search health="stale" OR health="no_data" | stats count as value'),
          "Instances behind", "value", ranges=[(None, GOOD), (1, WARNING)],
          description="No data for more than nifi_stale_factor intervals")
    ta = v.search("ds_ta_errors", r'''
index=_internal sourcetype=splunkd component=ExecProcessor "nifi.py" "status_code:"
| rex "status_code: (?<status_code>\d+)"
| eval login = if(searchmatch("get_token"), 1, 0)
| where tonumber(status_code) >= 400 AND NOT (status_code == "401" AND login == 0)
| eval code = case(login == 1, "login " . status_code, tonumber(status_code) >= 500, "5xx", true(), status_code)
''', name="TA HTTP errors")
    v.kpi("viz_ta", v.chain("ds_k_ta", ta, "| stats count as value"), "TA HTTP errors", "value",
          ranges=[(None, GOOD), (1, WARNING)])
    v.row(130, "viz_events", "viz_behind", "viz_ta")
    v.table("viz_matrix", v.search("ds_matrix", r'''
| tstats latest(_time) as last where `index_nifi` sourcetype=nifi:* earliest=-24h latest=now by host sourcetype
| append [| rest splunk_server=local count=0 /servicesNS/-/-/data/inputs/nifi | eval host = coalesce(host, title) | fields host interval]
| eventstats max(interval) as interval by host
| where isnotnull(sourcetype)
| eval interval = coalesce(interval, `nifi_default_interval`), age = now() - last,
       state = case(sourcetype LIKE "nifi:log:%" OR sourcetype LIKE "%bulletin%", "✓", age <= interval * `nifi_stale_factor`, "✓", age <= 3600, "! late", true(), "✕ " . tostring(round(age), "duration")),
       sourcetype = replace(sourcetype, "^nifi:", "")
| xyseries host sourcetype state
| rename host as Instance
''', earliest="-24h", latest="now"), "Last data per instance and source",
            "✓ on time · ! late (more than nifi_stale_factor intervals) · ✕ missing for that long · blank: not collected. Logs and bulletins arrive only when there is something to say, so they are never late",
            count=20)
    v.row(300, "viz_matrix")
    v.chart("viz_ta_time", "splunk.column", v.chain("ds_ta_time", ta, "| timechart span=1h count by code"),
            "TA HTTP errors by status code", "login 401: credentials · 403: permissions · 404: a wrong id · 5xx: NiFi. Expired-token 401s are renewed on the spot and not counted",
            stacked=True)
    v.table("viz_where", v.search("ds_where", r'''
| tstats count where index=* sourcetype=nifi:* by index sourcetype
| stats sum(count) as Events, dc(sourcetype) as Sourcetypes by index
| sort - Events | rename index as Index
'''), "Where NiFi data is", "Point the index_nifi macro at the index listed here", count=10)
    v.row(300, ("viz_ta_time", 7), ("viz_where", 5))
    return v


ALL = [overview, instance, components, bulletins, logs, cluster, alerts, collection]


def render():
    return {view.name + ".xml": view.xml() for view in (build() for build in ALL)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="exit 1 if the views drifted")
    args = parser.parse_args(argv)
    drifted = []
    for name, text in sorted(render().items()):
        path = os.path.join(VIEWS, name)
        current = open(path, encoding="utf-8").read() if os.path.isfile(path) else None
        if current != text:
            drifted.append(name)
            if not args.check:
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write(text)
    if args.check and drifted:
        print("out of date: %s -- run tools/gen_dashboards.py" % ", ".join(drifted))
        return 1
    if not args.check:
        print("wrote %d views (%d changed)" % (len(ALL), len(drifted)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
