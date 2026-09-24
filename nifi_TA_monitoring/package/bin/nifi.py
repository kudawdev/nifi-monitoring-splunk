import sys
import os
import re
try:
    import requests
    import urllib3
except ImportError as error:  # pragma: no cover - depends on the host Splunk
    # Deliberately NOT vendored into lib/. Every supported Splunk ships both:
    # measured 2026-09-17, requests 2.32.5 on Splunk 9.4 (Python 3.9.20) and
    # on 10.4 (Python 3.13.11), with urllib3 1.26.19 and 2.6.3 respectively.
    # Vendoring them would mean shipping charset_normalizer's compiled
    # extension, which is built for one platform and one Python version, so
    # the add-on would stop working on Windows, on ARM, and on any Splunk
    # whose Python is not the one it was built against. See defect B-15.
    sys.stderr.write(
        "nifi: this add-on uses 'requests' and 'urllib3' from Splunk's own "
        "Python, and %s. Every supported Splunk release ships both; on an "
        "installation where they are missing, add them to "
        "$SPLUNK_HOME/lib/python*/site-packages rather than to this app.\n"
        % error
    )
    raise
#import xml.etree.ElementTree as ElementTree
import time
import uuid
import unicodedata
import json
from urllib.parse import quote

# ucc-gen generates this: it puts the add-on's own lib/ first and, more to
# the point, drops every *other* add-on's bin/ from sys.path. Two add-ons with
# a module of the same name used to shadow each other depending on load order.
import import_declare_test  # noqa: F401
import splunklib.client as client
from splunklib.modularinput import EventWriter, Argument, Scheme, Event, Script
from solnlib.credentials import CredentialManager, CredentialNotExistException

class NiFiScript(Script):

    endpoints = [
            {"name":"endpoint_flow_status", "sourcetype":"nifi:api:flow_status", "path":"/flow/status"},
            {"name":"endpoint_system_diagnostics", "sourcetype":"nifi:api:system_diagnostics", "path":"/system-diagnostics"},
            {"name":"endpoint_processors_history", "sourcetype":"nifi:api:processors_history", "path":"/flow/processors/{id}/status/history"},
            {"name":"endpoint_process_groups_history", "sourcetype":"nifi:api:process_groups_history", "path":"/flow/process-groups/{id}/status/history"},
            {"name":"endpoint_bulletin_board", "sourcetype":"nifi:api:bulletin_board", "path":"/flow/bulletin-board"},
            # The json producer of the metrics endpoint appears in NiFi 1.16;
            # 1.15 and older only have the prometheus text format.
            {"name":"endpoint_flow_metrics", "sourcetype":"nifi:api:flow_metrics", "path":"/flow/metrics/json", "min_version":(1, 16, 0)}
        ]
    pid = 'Nifi Log pid="{}"'.format(uuid.uuid4())
    # Realm for the JWT in storage/passwords, so it cannot be confused with the
    # NiFi credential, which is stored with no realm.
    token_realm = "nifi_TA_monitoring:token"
    # Where the configuration form keeps the password. UCC's REST handler
    # encrypts every field declared `encrypted` into storage/passwords, keyed
    # by the input's stanza name, as a JSON object of those fields, and writes
    # a mask of asterisks into inputs.conf in its place.
    app_name = "nifi_TA_monitoring"
    ucc_realm = "__REST_CREDENTIAL__#nifi_TA_monitoring#data/inputs/nifi"
    # The password as inputs.conf holds it, when it is not the mask: a stanza
    # written by hand, as the test harness does. Set by stream_events.
    inline_password = None
    # Resolved once per process, like the token: one process serves one input.
    password_cache = None
    # The token for this process's input. use_single_instance is false, so one
    # process serves one input and an instance attribute is the right scope.
    token_cache = None
    # How long a detected NiFi version is trusted before /system-diagnostics
    # is polled for it again. It only changes when NiFi is upgraded, and the
    # call is otherwise pure waste on an input that does not index the
    # sourcetype (defect TA-4b).
    version_cache_seconds = 3600
    tls_verify = True
    nifi_version = None
    # Log level, read once per run from Configuration > Logging. Splunk's
    # modular input framework has no level of its own -- every EventWriter.log
    # line reaches splunkd.log -- and this add-on writes one INFO per request
    # per endpoint per interval. On an instance with several NiFis that is the
    # bulk of what it puts in _internal, and until now the only way to quieten
    # it was to stop collecting.
    log_level = 'INFO'
    # WARNING and CRITICAL are what the Logging tab offers; WARN and FATAL are
    # what splunklib's EventWriter emits. Same levels, two spellings.
    _log_levels = {'DEBUG': 10, 'INFO': 20, 'WARN': 30, 'WARNING': 30,
                   'ERROR': 40, 'CRITICAL': 50, 'FATAL': 50}
    # Whether this NiFi is a cluster node. Detected alongside the version and
    # cached with it: it is a static property of the deployment, so it does
    # not deserve a call per cycle (decision C-5).
    clustered = None

    # NiFi component identifiers are UUIDs; a mistyped or truncated id is the
    # most common configuration error and otherwise only shows up as a 404
    # buried in splunkd.log.
    component_id_pattern = re.compile(r'^[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$')

    @staticmethod
    def __redact(secret):
        """Render a credential safe for splunkd.log.

        Long values (a JWT) show their last 4 characters, enough to tell two
        tokens apart when debugging. Short values show nothing but a length,
        since the last 4 of a short secret gives away too much of it.
        """
        if not secret:
            return '<none>'
        if len(secret) < 16:
            return '<redacted, len {}>'.format(len(secret))
        return '...{} <len {}>'.format(secret[-4:], len(secret))

    # TLS verification is on unless the input turns it off. Historically every
    # request passed verify=False, which accepts any certificate: against a
    # NiFi served over HTTPS that lets anyone on the path read the credentials
    # and the bearer token. NiFi 2.x defaults to HTTPS, so this matters more
    # than it did.
    @classmethod
    def _log(cls, ew, level, message):
        """EventWriter.log, filtered by the configured level.

        A classmethod because the two places that log while parsing the input
        definition have no instance to hand, and because one process serves
        one input, so class scope and instance scope are the same thing here.
        Unknown levels pass: a typo in a conf file must not silence an error.
        """
        threshold = cls._log_levels.get(str(cls.log_level).upper(), 20)
        if cls._log_levels.get(level, 100) < threshold:
            return
        EventWriter.log(ew, level, message)

    def __load_log_level(self, ew, session_key):
        """Read Configuration > Logging, once, before anything else logs."""
        try:
            service = client.connect(token=session_key, owner='nobody',
                                     app='nifi_TA_monitoring')
            settings = service.confs['nifi_ta_monitoring_settings']
            level = settings['logging']['loglevel']
        except Exception as error:
            # Never fatal: a missing setting means the default, and saying so
            # at INFO would be logged at a level the operator may have just
            # turned off.
            EventWriter.log(ew, EventWriter.DEBUG, '{} Could not read the configured log level, using {}: {}'.format(self.pid, self.log_level, error))
            return
        if level and str(level).upper() in self._log_levels:
            type(self).log_level = str(level).upper()

    @staticmethod
    def _is_enabled(value, default=False):
        """Read a modular-input boolean, which arrives as 0/1 or true/false."""
        if value is None or value == '':
            return default
        return str(value).strip().lower() in ('1', 'true', 'yes', 'on')

    @staticmethod
    def __tls_hint(error):
        """Turn a certificate failure into an actionable message."""
        text = str(error).lower()
        if 'certificate' in text or 'sslerror' in text or 'ssl:' in text:
            return (' -- the NiFi certificate could not be verified. Point "CA bundle path" '
                    'at a bundle that trusts it, or uncheck "Verify TLS certificate" if you '
                    'accept an unverified connection.')
        return ''

    # Version detection. /system-diagnostics carries versionInfo.niFiVersion on
    # both the 1.x and 2.x lines, so one code path covers every supported
    # release. The metrics endpoint's VERSION_INFO registry would only work on
    # 2.x -- it answers 404 before 2.0 -- so it is not used for this.
    version_pattern = re.compile(r'^(\d+)\.(\d+)(?:\.(\d+))?')

    @classmethod
    def parse_version(cls, raw):
        """'2.11.0' -> (2, 11, 0). Returns None when it cannot be read."""
        match = cls.version_pattern.match((raw or '').strip())
        if not match:
            return None
        return tuple(int(part) if part else 0 for part in match.groups())

    @staticmethod
    def version_info_of(diagnostics_json):
        """Pull versionInfo out of a /system-diagnostics payload."""
        try:
            return json.loads(diagnostics_json)['systemDiagnostics']['aggregateSnapshot']['versionInfo']
        except (TypeError, ValueError, KeyError):
            return None

    # Bulletins. /flow/bulletin-board accepts ?after=<id> on both the 1.x and
    # 2.x lines, so each poll asks only for what it has not seen. That removes
    # duplicates, but it cannot recover a bulletin that NiFi already dropped
    # from the board: the board holds a limited window (5 minutes by default),
    # so an interval longer than that window loses events. Clients that cannot
    # afford any loss should keep using SiteToSiteBulletinReportingTask, which
    # pushes instead of being polled.
    bulletin_page_limit = 1000

    def __checkpoint_path(self, input_name, name):
        """A file under Splunk's checkpoint dir, which survives restarts."""
        directory = (self._input_definition.metadata or {}).get('checkpoint_dir')
        if not directory:
            return None
        safe = re.sub(r'[^A-Za-z0-9_.-]', '_', input_name)
        return os.path.join(directory, '{}.{}'.format(safe, name))

    def __read_checkpoint(self, ew, input_name, name):
        path = self.__checkpoint_path(input_name, name)
        if not path or not os.path.isfile(path):
            return None
        try:
            with open(path) as handle:
                return handle.read().strip() or None
        except Exception as error:
            self._log(ew, EventWriter.WARN, '{} Could not read checkpoint {}: {}'.format(self.pid, name, error))
            return None

    def __write_checkpoint(self, ew, input_name, name, value):
        path = self.__checkpoint_path(input_name, name)
        if not path:
            return
        try:
            with open(path, 'w') as handle:
                handle.write(str(value))
        except Exception as error:
            self._log(ew, EventWriter.WARN, '{} Could not write checkpoint {}: {}'.format(self.pid, name, error))

    def __token_key(self, input_name):
        return unicodedata.normalize('NFKD', input_name).replace(' ', '')

    def __cached_version(self, ew, input_name):
        """The last detected version info, if it is still fresh.

        Kept in the checkpoint dir rather than in memory: the modular input is
        a process per cycle, so an in-memory cache would never survive to be
        used.
        """
        raw = self.__read_checkpoint(ew, input_name, 'version')
        if not raw:
            return None
        try:
            record = json.loads(raw)
            if time.time() - float(record.get('at', 0)) > self.version_cache_seconds:
                return None
            info = record.get('info') or {}
            return info if info.get('niFiVersion') else None
        except Exception:
            return None

    def __cache_version(self, ew, input_name, version_info, clustered=False):
        record = dict(version_info)
        record['_clustered'] = bool(clustered)
        self.__write_checkpoint(ew, input_name, 'version', json.dumps(
            {'at': time.time(), 'info': record}))

    def __read_token(self, ew, session_key, input_name):
        """The stored JWT for this input.

        It used to live in a .env inside the app directory, which lost it on
        every reinstall and, because dotenv.find_dotenv() walks up from the
        working directory, could pick up an unrelated file under $SPLUNK_HOME.
        Worse for more than one instance: every input's process wrote that same
        file non-atomically, so two renewing at once could clobber each other.

        Cached for the life of the process, which also makes this cheaper than
        what it replaces -- that reloaded the .env on every request.
        """
        if self.token_cache is not None:
            return self.token_cache
        key = self.__token_key(input_name)
        try:
            service = client.connect(token=session_key)
            for stored in service.storage_passwords:
                if stored.realm == self.token_realm and stored.username == key:
                    self.token_cache = stored.content.clear_password
                    return self.token_cache
        except Exception as error:
            self._log(ew, EventWriter.WARN, '{} Could not read the stored token: {}'.format(self.pid, error))
        return None

    def __write_token(self, ew, session_key, input_name, token):
        """Store the renewed JWT, replacing whatever was there."""
        key = self.__token_key(input_name)
        self.token_cache = token
        try:
            service = client.connect(token=session_key)
            for stored in service.storage_passwords:
                if stored.realm == self.token_realm and stored.username == key:
                    service.storage_passwords.delete(username=key, realm=self.token_realm)
                    break
            service.storage_passwords.create(token, key, self.token_realm)
        except Exception as error:
            self._log(ew, EventWriter.WARN, '{} Could not store the renewed token: {}'.format(self.pid, error))

    @staticmethod
    def bulletins_of(payload):
        """The bulletin entries out of a /flow/bulletin-board response."""
        try:
            return json.loads(payload)['bulletinBoard']['bulletins'] or []
        except (TypeError, ValueError, KeyError):
            return None

    @staticmethod
    def highest_bulletin_id(bulletins):
        """The largest entry id, to resume from on the next poll."""
        ids = []
        for entry in bulletins:
            for candidate in (entry.get('id'), (entry.get('bulletin') or {}).get('id')):
                if isinstance(candidate, int):
                    ids.append(candidate)
                    break
        return max(ids) if ids else None

    # Flow metrics. GET /flow/metrics/json returns Prometheus' data model
    # serialised to JSON: labelNames and labelValues are *parallel arrays*, so
    # INDEXED_EXTRACTIONS would index them as two unrelated multivalue fields.
    # The TA zips them into one flat event per sample instead.
    #
    # Volume is the reason this endpoint is off by default: an idle NiFi
    # already emits 60 samples (~14 KB) per poll, and ALL_COMPONENTS scales
    # that with every processor in the flow.
    metrics_registries_all = ('NIFI', 'JVM', 'BULLETIN', 'CONNECTION', 'CLUSTER')
    metrics_registries_2x = ('VERSION_INFO',)
    metrics_strategies = ('ALL_COMPONENTS', 'ALL_PROCESS_GROUPS')
    metrics_default_strategy = 'ALL_PROCESS_GROUPS'

    @classmethod
    def known_registries(cls, version=None):
        """Registries this NiFi accepts. VERSION_INFO 404s before 2.0."""
        registries = list(cls.metrics_registries_all)
        if version is None or version >= (2, 0, 0):
            registries += list(cls.metrics_registries_2x)
        return tuple(registries)

    def metrics_query(self, input_item):
        """Build the query string for /flow/metrics/json from the input."""
        params = []

        requested = self._split_ids(input_item.get('metrics_registries') or '')
        allowed = self.known_registries(self.nifi_version)
        for registry in requested:
            name = registry.strip().upper()
            if name in allowed:
                params.append(('includedRegistries', name))

        strategy = (input_item.get('metrics_strategy') or '').strip().upper()
        if strategy not in self.metrics_strategies:
            strategy = self.metrics_default_strategy
        params.append(('flowMetricsReportingStrategy', strategy))

        sample_filter = (input_item.get('metrics_sample_filter') or '').strip()
        if sample_filter:
            params.append(('sampleName', sample_filter))

        return '&'.join('{}={}'.format(key, quote(value, safe='')) for key, value in params)

    @staticmethod
    def cluster_nodes_of(payload):
        """One record per node out of /controller/cluster.

        Each carries address, status, roles (Primary Node / Cluster
        Coordinator), heartbeat and its own queue and thread counts, which is
        what answers "is my cluster whole, and which node coordinates".
        """
        try:
            nodes = json.loads(payload)['cluster']['nodes']
        except (TypeError, ValueError, KeyError):
            return None
        return nodes or []

    @staticmethod
    def node_snapshots_of(payload):
        """The per-node diagnostics out of /system-diagnostics?nodewise=true.

        Each snapshot has the same shape as aggregateSnapshot -- measured, not
        assumed -- so the 17 fields the datamodel already declares work per
        node with no extra extraction (decision C-4). The node's address is
        folded in so an event says which node it describes.
        """
        try:
            diagnostics = json.loads(payload)['systemDiagnostics']
        except (TypeError, ValueError, KeyError):
            return None
        out = []
        for entry in diagnostics.get('nodeSnapshots') or []:
            snapshot = entry.get('snapshot')
            if not snapshot:
                continue
            out.append({
                'node': entry.get('address'),
                'nodeId': entry.get('nodeId'),
                'apiPort': entry.get('apiPort'),
                'systemDiagnostics': {'aggregateSnapshot': snapshot},
            })
        return out

    @staticmethod
    def is_clustered(payload):
        """Whether /flow/cluster/summary says this NiFi is a cluster node."""
        try:
            return bool(json.loads(payload)['clusterSummary']['clustered'])
        except (TypeError, ValueError, KeyError):
            return None

    @staticmethod
    def flatten_samples(payload):
        """Zip each sample's parallel label arrays into one flat dict.

        Empty label values are dropped: parent_id alone is empty on most
        samples, and an empty string reads no differently from an absent
        field in Splunk while costing bytes on every event.
        """
        try:
            samples = json.loads(payload)['samples']
        except (TypeError, ValueError, KeyError):
            return None
        if samples is None:
            return []

        flattened = []
        for sample in samples:
            names = sample.get('labelNames') or []
            values = sample.get('labelValues') or []
            flat = {'metric_name': sample.get('name'), 'metric_value': sample.get('value')}
            for name, value in zip(names, values):
                if value not in (None, ''):
                    flat[name] = value
            flattened.append(flat)
        return flattened

    def __supported(self, endpoint, ew):
        """Whether this NiFi is new enough for the endpoint.

        Endpoints without a min_version are assumed to exist everywhere. When
        the version could not be detected, only those are collected: guessing
        would mean logging a 404 as an error on every cycle.
        """
        minimum = endpoint.get('min_version')
        if minimum is None:
            return True
        if self.nifi_version is None:
            return False
        if self.nifi_version >= minimum:
            return True
        self._log(ew, EventWriter.INFO, '{} Skipping {}: requires NiFi {} and this instance is older'.format(
            self.pid, endpoint.get('name'), '.'.join(str(part) for part in minimum)))
        return False

    @classmethod
    def __safe_item(cls, input_item):
        """A copy of the input settings with the credential redacted.

        The raw dict carries the cleartext password on the first run, before
        it is moved into storage/passwords and masked.
        """
        return {
            key: (cls.__redact(value) if key == 'password' else value)
            for key, value in sorted(input_item.items())
        }

    def _tls_verify(self, input_item):
        """The value to hand requests' `verify`: a CA bundle, True, or False."""
        if not self._is_enabled(input_item.get('verify_tls'), default=True):
            return False
        ca_bundle = (input_item.get('ca_bundle') or '').strip()
        return ca_bundle or True

    @staticmethod
    def _split_ids(raw):
        """Split a comma/newline separated id list, dropping empty entries."""
        return [part.strip() for part in raw.replace('\n', ',').split(',') if part.strip()]

    # Custom endpoints. The fixed `endpoints` table above covers what the app
    # ships with; a customer with a NiFi endpoint outside that list has no way
    # to collect it without a code change. `custom_endpoints` lets them add
    # any number of additional REST paths, each tagged with the sourcetype
    # they want it indexed under -- the TA does not know their shape, so it
    # cannot pick a sourcetype for them the way it does for the built-in six.
    #
    # The user names the endpoint, not the sourcetype: `queue_stats`, not
    # `nifi:api:custom:queue_stats`. The prefix carries no information they
    # could get wrong usefully, and writing it out thirteen times -- the size
    # this field is actually used at -- is thirteen chances to typo it.
    #
    # It is also the only thing keeping them out of the add-on's own
    # namespace. The first version accepted any string of legal characters, so
    # `nifi:api:flow_status,/flow/about` saved without complaint and the next
    # poll would have written /flow/about bodies into the sourcetype the NIFI
    # datamodel and every overview panel read -- silently, and indistinguishable
    # from real data once indexed (defect CE-5).
    custom_prefix = 'nifi:api:custom:'
    custom_name_pattern = re.compile(r'^[A-Za-z0-9_.-]+$')

    @classmethod
    def custom_sourcetype(cls, name):
        """The sourcetype a custom endpoint's name resolves to.

        Idempotent: the long form is accepted so a configuration written
        against an earlier build, or copied out of an index, still means what
        it says.
        """
        name = (name or '').strip()
        if name.startswith(cls.custom_prefix):
            return name
        return cls.custom_prefix + name

    @classmethod
    def _validate_custom_endpoint(cls, sourcetype, path):
        """None when (sourcetype, path) is usable, else why it is not."""
        if not sourcetype:
            return 'sourcetype is empty'
        name = sourcetype[len(cls.custom_prefix):] \
            if sourcetype.startswith(cls.custom_prefix) else sourcetype
        if ':' in name:
            if sourcetype.startswith('nifi:'):
                return ("'{}' is a sourcetype this add-on ships; a custom "
                        "endpoint writing to it would mix its response into "
                        "data the dashboards read. Give the endpoint a name "
                        "instead, and it is indexed under {}<name>"
                        .format(sourcetype, cls.custom_prefix))
            return ("'{}' is not a name: a custom endpoint is named, not "
                    "given a sourcetype, and is always indexed under "
                    "{}<name>".format(sourcetype, cls.custom_prefix))
        if not name:
            return 'sourcetype is empty'
        if not cls.custom_name_pattern.match(name):
            return ("name '{}' must contain only letters, digits, '_', '.' "
                    "or '-'".format(name))
        if not path:
            return 'path is empty'
        if '://' in path:
            return "path '{}' must be a relative path, not a full URL".format(path)
        if not path.startswith('/'):
            return "path '{}' must start with / and be relative to the NiFi API URL".format(path)
        if any(character.isspace() for character in path):
            return "path '{}' must not contain whitespace".format(path)
        if '{' in path or '}' in path:
            # Accepting it and then requesting the path literally is a silent
            # 404: the built-in history endpoints do substitute an id, they
            # are configured a few fields up on the same screen, and it is a
            # reasonable thing to assume carries over here (defect CE-3).
            return ("path '{}' cannot contain a placeholder: custom endpoints are "
                    "requested exactly as written. Use the actual id, or the "
                    "Status History fields above, which substitute one"
                    .format(path))
        return None

    @classmethod
    def _parse_custom_endpoints(cls, raw, ew=None):
        """Parse `custom_endpoints`: one '<sourcetype>,<path>' per line.

        Lenient by design -- this runs on every poll, against a value that
        was already accepted by validate_input at save time. A line that is
        no longer valid (hand-edited inputs.conf) is skipped with a WARN
        rather than aborting the whole cycle.
        """
        endpoints = []
        for line_number, line in enumerate((raw or '').splitlines(), start=1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if ',' not in line:
                if ew is not None:
                    cls._log(ew, EventWriter.WARN, "{} Ignoring custom endpoint on line {}: expected '<sourcetype>,<path>'".format(cls.pid, line_number))
                continue
            sourcetype, path = (part.strip() for part in line.split(',', 1))
            error = cls._validate_custom_endpoint(sourcetype, path)
            if error:
                if ew is not None:
                    cls._log(ew, EventWriter.WARN, '{} Ignoring custom endpoint on line {}: {}'.format(cls.pid, line_number, error))
                continue
            endpoints.append({'sourcetype': cls.custom_sourcetype(sourcetype),
                              'path': path})
        return endpoints


    def get_scheme(self):
        scheme = Scheme("NiFi")
        scheme.description = "Get statistics from NiFi Instance"
        scheme.use_external_validation = True
        scheme.use_single_instance = False

        name_argument = Argument(
            name="name",
            description="NiFi Instance Name",
            title="Name",
            data_type=Argument.data_type_string,
            required_on_edit=True,
            required_on_create=True
        )
        scheme.add_argument(name_argument)

        url_argument = Argument(
            name="api_url",
            description="NiFi instance API URL",
            title="NiFi API URL",
            data_type=Argument.data_type_string,
            required_on_edit=True,
            required_on_create=True
        )
        scheme.add_argument(url_argument)

        enpoint_system_diagnostics_argument = Argument(
            name="endpoint_system_diagnostics",
            description="System Diagnostics",
            title="System Diagnostics",
            data_type=Argument.data_type_boolean,
            required_on_edit=True,
            required_on_create=True
        )
        scheme.add_argument(enpoint_system_diagnostics_argument)

        endpoint_flow_status_argument = Argument(
            name="endpoint_flow_status",
            description="Flow Status",
            title="Flow Status",
            data_type=Argument.data_type_boolean,
            required_on_edit=True,
            required_on_create=True
        )
        scheme.add_argument(endpoint_flow_status_argument)

        endpoint_processors_history_argument = Argument(
            name="endpoint_processors_history",
            description="List of Processors ID",
            title="List of Processors ID",
            data_type=Argument.data_type_string,
            required_on_edit=False,
            required_on_create=False
        )
        scheme.add_argument(endpoint_processors_history_argument)

        endpoint_process_groups_history_argument = Argument(
            name="endpoint_process_groups_history",
            description="List of Process Groups ID",
            title="List of Process Groups ID",
            data_type=Argument.data_type_string,
            required_on_edit=False,
            required_on_create=False
        )
        scheme.add_argument(endpoint_process_groups_history_argument)
        
        endpoint_bulletin_board_argument = Argument(
            name="endpoint_bulletin_board",
            description="Poll the bulletin board for individual bulletins. Enabled by default. The board only keeps a short window, so an interval longer than that window can miss bulletins; use SiteToSiteBulletinReportingTask instead when no loss is acceptable.",
            title="Bulletin Board",
            data_type=Argument.data_type_boolean,
            required_on_edit=False,
            required_on_create=False
        )
        scheme.add_argument(endpoint_bulletin_board_argument)

        endpoint_flow_metrics_argument = Argument(
            name="endpoint_flow_metrics",
            description="Collect flow metrics from /flow/metrics/json (NiFi 1.16 and later). Disabled by default: an idle instance emits around 60 samples per poll and ALL_COMPONENTS scales that with every processor in the flow, so review the volume before enabling.",
            title="Flow Metrics",
            data_type=Argument.data_type_boolean,
            required_on_edit=False,
            required_on_create=False
        )
        scheme.add_argument(endpoint_flow_metrics_argument)

        metrics_registries_argument = Argument(
            name="metrics_registries",
            description="Which metric registries to collect, comma separated: NIFI, JVM, BULLETIN, CONNECTION, CLUSTER, and VERSION_INFO on NiFi 2.x. Empty collects all of them.",
            title="Metric registries",
            data_type=Argument.data_type_string,
            required_on_edit=False,
            required_on_create=False
        )
        scheme.add_argument(metrics_registries_argument)

        metrics_strategy_argument = Argument(
            name="metrics_strategy",
            description="ALL_PROCESS_GROUPS (default) reports per process group; ALL_COMPONENTS reports per component, which is far more detailed and far larger.",
            title="Metric reporting strategy",
            data_type=Argument.data_type_string,
            required_on_edit=False,
            required_on_create=False
        )
        scheme.add_argument(metrics_strategy_argument)

        metrics_sample_filter_argument = Argument(
            name="metrics_sample_filter",
            description="Regular expression matched against the metric name, to collect only part of what NiFi exposes. e.g. nifi_jvm.*",
            title="Metric name filter",
            data_type=Argument.data_type_string,
            required_on_edit=False,
            required_on_create=False
        )
        scheme.add_argument(metrics_sample_filter_argument)

        custom_endpoints_argument = Argument(
            name="custom_endpoints",
            description=(
                "Additional NiFi REST endpoints to poll, one per line as 'sourcetype,path' "
                "(e.g. nifi:api:custom:queue_stats,/flow/connections/1234-5678-90ab-cdef/status). "
                "The path is relative to the NiFi API URL above. Splunk indexes the raw response "
                "under the sourcetype given; add your own props.conf if you need field extraction."
            ),
            title="Custom endpoints",
            data_type=Argument.data_type_string,
            required_on_edit=False,
            required_on_create=False
        )
        scheme.add_argument(custom_endpoints_argument)

        auth_type_argument = Argument(
            name="auth_type",
            description="Auth Type",
            title="Auth type",
            data_type=Argument.data_type_string,
            required_on_edit=True,
            required_on_create=True
        )
        scheme.add_argument(auth_type_argument)

        username_argument = Argument(
            name="username",
            description="Authentication User",
            title="Username",
            data_type=Argument.data_type_string,
            required_on_edit=False,
            required_on_create=False
        )
        scheme.add_argument(username_argument)

        password_argument = Argument(
            name="password",
            description="Authentication Password",
            title="Password",
            data_type=Argument.data_type_string,
            required_on_edit=False,
            required_on_create=False
        )
        scheme.add_argument(password_argument)

        verify_tls_argument = Argument(
            name="verify_tls",
            description="Verify the NiFi TLS certificate. Leave enabled unless the instance uses a self-signed certificate that cannot be trusted through a CA bundle.",
            title="Verify TLS certificate",
            data_type=Argument.data_type_boolean,
            required_on_edit=False,
            required_on_create=False
        )
        scheme.add_argument(verify_tls_argument)

        ca_bundle_argument = Argument(
            name="ca_bundle",
            description="Path to a CA bundle used to verify the NiFi certificate. Leave empty to use the system trust store.",
            title="CA bundle path",
            data_type=Argument.data_type_string,
            required_on_edit=False,
            required_on_create=False
        )
        scheme.add_argument(ca_bundle_argument)

        # The form's Test connection button. It holds no value and the input
        # never reads it, but ucc-gen writes every form field into
        # inputs.conf.spec, and splunkd makes a spec parameter the scheme does
        # not declare required on create -- so the form could not save an
        # input at all: "The following required arguments are missing:
        # test_connection".
        test_connection_argument = Argument(
            name="test_connection",
            description="The form's Test connection button. Not a setting.",
            title="Test connection",
            data_type=Argument.data_type_string,
            required_on_edit=False,
            required_on_create=False
        )
        scheme.add_argument(test_connection_argument)

        return scheme


    def validate_input(self, validation_definition):
        params = validation_definition.parameters

        api_url = (params.get("api_url") or "").strip()
        if not api_url:
            raise ValueError("NiFi API URL is required")
        if not api_url.startswith(("http://", "https://")):
            raise ValueError("NiFi API URL must start with http:// or https://")

        auth_type = (params.get("auth_type") or "").strip()
        if auth_type not in ("none", "basic"):
            raise ValueError("Auth type must be either 'none' or 'basic'")

        if auth_type == "basic":
            if not (params.get("username") or "").strip():
                raise ValueError("Username is required when auth type is 'basic'")
            if not (params.get("password") or "").strip():
                raise ValueError("Password is required when auth type is 'basic'")

        interval = (params.get("interval") or "").strip()
        # Splunk also accepts a cron expression here; only check plain numbers.
        if interval and interval.isdigit() and int(interval) <= 0:
            raise ValueError("Interval must be greater than 0 seconds")

        strategy = (params.get("metrics_strategy") or "").strip().upper()
        if strategy and strategy not in self.metrics_strategies:
            raise ValueError(
                "Metric reporting strategy must be one of: {}".format(
                    ", ".join(self.metrics_strategies))
            )

        for registry in self._split_ids(params.get("metrics_registries") or ""):
            if registry.strip().upper() not in self.known_registries():
                raise ValueError(
                    "Unknown metric registry '{}'; known: {}".format(
                        registry, ", ".join(self.known_registries()))
                )

        sample_filter = (params.get("metrics_sample_filter") or "").strip()
        if sample_filter:
            try:
                re.compile(sample_filter)
            except re.error as error:
                raise ValueError("Metric name filter is not a valid regular expression: {}".format(error))

        ca_bundle = (params.get("ca_bundle") or "").strip()
        if ca_bundle and not os.path.isfile(ca_bundle):
            raise ValueError("CA bundle not found: {}".format(ca_bundle))
        if ca_bundle and not self._is_enabled(params.get("verify_tls"), default=True):
            raise ValueError(
                "A CA bundle was given but TLS verification is disabled; "
                "enable verification or clear the CA bundle"
            )

        for field, label in (("endpoint_processors_history", "processor"),
                             ("endpoint_process_groups_history", "process group")):
            for component_id in self._split_ids(params.get(field) or ""):
                if not self.component_id_pattern.match(component_id):
                    raise ValueError(
                        "Invalid {} id '{}': expected a UUID".format(label, component_id)
                    )

        # Every bad line at once. Stopping at the first meant fixing one,
        # saving, and being told about the next -- tedious with three
        # mistakes in a list of thirteen, which is the size this field is
        # actually used at.
        problems = []
        for line_number, line in enumerate((params.get("custom_endpoints") or "").splitlines(), start=1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if ',' not in line:
                problems.append(
                    "line {} must be 'sourcetype,path': {}".format(line_number, line))
                continue
            sourcetype, path = (part.strip() for part in line.split(',', 1))
            error = self._validate_custom_endpoint(sourcetype, path)
            if error:
                problems.append("line {}: {}".format(line_number, error))
        if problems:
            raise ValueError("Custom endpoints -- %s" % "; ".join(problems))


    def stream_events(self, inputs, ew):

        input_name, input_item = inputs.inputs.popitem()

        session_key = self._input_definition.metadata['session_key']

        # Before the first line is written, or the level cannot filter it.
        self.__load_log_level(ew, session_key)
        self._log(ew, EventWriter.INFO, '{} Started Stream Events'.format(self.pid))
        
        base_url   = input_item.get("api_url")
        auth_type  = input_item.get("auth_type")
        username   = input_item.get("username", None)
        password   = input_item.get("password", None)
        processors = input_item.get("endpoint_processors_history", None)
        process_groups = input_item.get("endpoint_process_groups_history", None)

        # Removed in 2.0.0: nothing in the app ever consumed this sourcetype,
        # so it was ingestion billed against the licence for data no panel
        # showed. Say so once rather than ignoring the leftover setting.
        if input_item.get('endpoint_site_to_site') is not None:
            self._log(ew, EventWriter.WARN, '{} endpoint_site_to_site was removed: nothing consumed nifi:api:site_to_site. The setting is ignored and can be deleted from inputs.conf'.format(self.pid))

        self.tls_verify = self._tls_verify(input_item)
        if self.tls_verify is False:
            # Only silence the warning the user has explicitly accepted.
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            self._log(ew, EventWriter.WARN, '{} TLS certificate verification is DISABLED for this input: credentials and the bearer token can be read by anyone able to intercept the connection'.format(self.pid))

        kind, iname = input_name.split("://")
        # Every collector reads the host from input_item, so it is settled
        # here, once, for all of them.
        input_item["host"] = self._event_host(input_item.get("host"), iname)

        self._log(ew, EventWriter.INFO, "{} Started Nifi Get Data for input: input_name:{}, input_item:{}".format(self.pid, input_name, self.__safe_item(input_item)))

        # The add-on no longer stores or masks the password itself. It used
        # to, from before the form was generated by UCC: on the first run it
        # moved a cleartext password into storage/passwords under the NiFi
        # username and rewrote inputs.conf with its own mask. UCC now does
        # both when the input is saved -- differently -- so on an input
        # created from the form this code read UCC's mask as a new password,
        # failed to store it ("Password cannot contain all * characters"),
        # found no credential of its own and never authenticated.
        if auth_type == 'basic' and not self._is_mask(password):
            self.inline_password = password

        
        # Detect the NiFi version before deciding what to collect.
        #
        # TA-4b asked for /system-diagnostics to become optional on NiFi 2.x,
        # where the metrics endpoint already covers the three repositories.
        # It cannot: the call is how the version is detected (TA-3), so it
        # happens whether or not the sourcetype is indexed. What can be
        # avoided is paying for it on every cycle. When the input does not
        # index system_diagnostics and the version is already known and
        # fresh, the call is skipped entirely; when it does index it, the
        # response is reused so the endpoint is never fetched twice.
        wants_diagnostics = input_item.get('endpoint_system_diagnostics') == '1'
        cached = self.__cached_version(ew, input_name)
        diagnostics = None
        version_info = None

        if wants_diagnostics or not cached:
            diagnostics = self.__get_request(ew, base_url, "/system-diagnostics", auth_type, username, iname, session_key)
            version_info = self.version_info_of(diagnostics)
            self.nifi_version = self.parse_version((version_info or {}).get('niFiVersion'))
            summary = self.__get_request(ew, base_url, "/flow/cluster/summary", auth_type, username, iname, session_key)
            self.clustered = bool(self.is_clustered(summary))
            if version_info:
                self.__cache_version(ew, input_name, version_info, self.clustered)
        else:
            version_info = cached
            self.nifi_version = self.parse_version(cached.get('niFiVersion'))
            self.clustered = bool(cached.get('_clustered'))
            self._log(ew, EventWriter.INFO, '{} Using the cached NiFi version {}; /system-diagnostics not polled this cycle'.format(
                self.pid, cached.get('niFiVersion')))

        if self.nifi_version and diagnostics is not None:
            self._log(ew, EventWriter.INFO, '{} Detected NiFi {} (Java {})'.format(
                self.pid, version_info.get('niFiVersion'), version_info.get('javaVersion')))
            ew.write_event(Event(
                sourcetype="nifi:api:version_info",
                stanza=input_name,
                data=json.dumps(version_info),
                host=input_item.get("host")
            ))
        elif not self.nifi_version:
            self._log(ew, EventWriter.WARN, '{} Could not detect the NiFi version from /system-diagnostics; version-dependent endpoints will be skipped'.format(self.pid))

        if self.clustered:
            self._log(ew, EventWriter.INFO, '{} NiFi reports it is clustered; collecting per-node data'.format(self.pid))
            self.__collect_cluster(ew, base_url, auth_type, username, iname,
                                   session_key, input_name, input_item)

        for ep in self.endpoints:
            if not self.__supported(ep, ew):
                continue
            path = ep.get("path")
            sourcetype = ep.get("sourcetype")
            self._log(ew, EventWriter.INFO, '{} Request endpoint: {}'.format(self.pid, ep))
            
            if ep.get('name') == 'endpoint_flow_metrics':
                if not self._is_enabled(input_item.get('endpoint_flow_metrics'), default=False):
                    continue
                self.__collect_flow_metrics(ew, base_url, path, sourcetype, auth_type,
                                            username, iname, session_key, input_name, input_item)
                continue

            if ep.get('name') == 'endpoint_bulletin_board':
                if input_item.get('endpoint_bulletin_board') not in ('1', None, ''):
                    continue
                self.__collect_bulletins(ew, base_url, path, sourcetype, auth_type,
                                         username, iname, session_key, input_name, input_item)
                continue

            if input_item.get(ep.get('name')) == '1':
                try:
                    if path == "/system-diagnostics":
                        response = diagnostics   # already fetched for version detection
                    else:
                        response = self.__get_request(ew, base_url, path, auth_type, username, iname, session_key)
                    if response is None:
                        # The request failed and said so in the log. Writing
                        # the event anyway is how an error body ends up
                        # indexed as data (CE-1).
                        continue
                    self._log(ew, EventWriter.DEBUG, '{} Response: {}'.format(self.pid, response))
                    event = Event(
                        sourcetype=sourcetype,
                        stanza=input_name,
                        data=response,
                        host=input_item.get("host")
                    )
                    ew.write_event(event)
                except Exception as e:
                    self._log(ew, EventWriter.ERROR, '{} There was an error when request: {}'.format(self.pid, e))
            
            elif (ep.get('name') == 'endpoint_processors_history') and (processors):
                plist = self._split_ids(processors)
                self._log(ew, EventWriter.INFO, '{} list of plist: {}'.format(self.pid, plist))
                for p in plist:
                    new_path = path.format(id=p)
                    self._log(ew, EventWriter.INFO, '{} endpoint_processors_history: {}'.format(self.pid, p))
                    try:
                        response = self.__get_request(ew, base_url, new_path, auth_type, username, iname, session_key)
                        self._log(ew, EventWriter.DEBUG, '{} Response: {}'.format(self.pid, response))
                        data_json = json.loads(response)
                        if "aggregateSnapshots" in data_json["statusHistory"]:
                            data_json["statusHistory"]["aggregateSnapshots"] = data_json["statusHistory"]["aggregateSnapshots"][-1:]

                        data_str = json.dumps(data_json)
                        event = Event(
                            sourcetype=sourcetype,
                            stanza=input_name,
                            data=data_str,
                            host=input_item.get("host")
                        )
                        ew.write_event(event)
                    except Exception as e:
                        self._log(ew, EventWriter.ERROR, '{} There was an error when request: {}'.format(self.pid, e))

            elif (ep.get('name') == 'endpoint_process_groups_history') and (process_groups):
                plist = self._split_ids(process_groups)
                self._log(ew, EventWriter.INFO, '{} list of plist: {}'.format(self.pid, plist))
                for p in plist:
                    new_path = path.format(id=p)
                    self._log(ew, EventWriter.INFO, '{} endpoint_process_groups_history: {}'.format(self.pid, p))
                    try:
                        response = self.__get_request(ew, base_url, new_path, auth_type, username, iname, session_key)
                        self._log(ew, EventWriter.DEBUG, '{} Response: {}'.format(self.pid, response))
                        data_json = json.loads(response)
                        if "aggregateSnapshots" in data_json["statusHistory"]:
                            data_json["statusHistory"]["aggregateSnapshots"] = data_json["statusHistory"]["aggregateSnapshots"][-1:]

                        data_str = json.dumps(data_json)
                        event = Event(
                            sourcetype=sourcetype,
                            stanza=input_name,
                            data=data_str,
                            host=input_item.get("host")
                        )
                        ew.write_event(event)
                    except Exception as e:
                        self._log(ew, EventWriter.ERROR, '{} There was an error when request: {}'.format(self.pid, e))
                        
            else:
                self._log(ew, EventWriter.INFO, 'there wasnt an endpoint detected: ')
                pass

        for custom in self._parse_custom_endpoints(input_item.get('custom_endpoints') or '', ew):
            self.__collect_custom_endpoint(ew, base_url, custom, auth_type, username, iname,
                                           session_key, input_name, input_item)

    def __collect_custom_endpoint(self, ew, base_url, custom, auth_type, username, iname,
                                  session_key, input_name, input_item):
        """Poll one user-declared endpoint and pass its response through as-is."""
        self._log(ew, EventWriter.INFO, '{} Request custom endpoint: {}'.format(self.pid, custom))
        try:
            response = self.__get_request(ew, base_url, custom['path'], auth_type, username, iname, session_key)
            if response is None:
                # Nothing usable came back, and __get_request already logged
                # why. A path that does not exist used to produce one event
                # per poll carrying the 404 body, under the sourcetype the
                # user chose, so their index said the endpoint was working.
                self._log(ew, EventWriter.WARN, "{} Custom endpoint '{}' returned nothing usable; no event written".format(self.pid, custom['path']))
                return
            self._log(ew, EventWriter.DEBUG, '{} Response: {}'.format(self.pid, response))
            event = Event(
                sourcetype=custom['sourcetype'],
                stanza=input_name,
                data=response,
                host=input_item.get("host")
            )
            ew.write_event(event)
        except Exception as e:
            self._log(ew, EventWriter.ERROR, "{} There was an error requesting custom endpoint '{}': {}".format(self.pid, custom['path'], e))

    def __collect_cluster(self, ew, base_url, auth_type, username, iname,
                          session_key, input_name, input_item):
        """Per-node data, which only exists on a cluster.

        Two sourcetypes, both one event per node (decision C-1: the cluster is
        the instance and the node is a dimension, so `host` keeps meaning the
        thing the operator configured and `node` says which member it is).

        `/controller/cluster` answers whether the cluster is whole and which
        node coordinates; the per-node diagnostics come from the nodewise form
        of an endpoint already being called, so they cost one extra request,
        not one per node.
        """
        host = input_item.get("host")

        nodes_raw = self.__get_request(ew, base_url, "/controller/cluster", auth_type,
                                       username, iname, session_key)
        nodes = self.cluster_nodes_of(nodes_raw)
        if nodes is None:
            self._log(ew, EventWriter.WARN, '{} Could not read /controller/cluster'.format(self.pid))
        else:
            connected = sum(1 for n in nodes if n.get('status') == 'CONNECTED')
            self._log(ew, EventWriter.INFO, '{} Cluster: {} of {} nodes connected'.format(
                self.pid, connected, len(nodes)))
            for node in nodes:
                event = dict(node)
                event['node'] = node.get('address')
                event['clusterNodeCount'] = len(nodes)
                event['clusterConnectedNodeCount'] = connected
                ew.write_event(Event(sourcetype="nifi:api:cluster_nodes",
                                     stanza=input_name, data=json.dumps(event), host=host))

        wise_raw = self.__get_request(ew, base_url, "/system-diagnostics?nodewise=true",
                                      auth_type, username, iname, session_key)
        snapshots = self.node_snapshots_of(wise_raw)
        if not snapshots:
            self._log(ew, EventWriter.WARN, '{} No per-node diagnostics returned'.format(self.pid))
            return
        for snapshot in snapshots:
            ew.write_event(Event(sourcetype="nifi:api:node_diagnostics",
                                 stanza=input_name, data=json.dumps(snapshot), host=host))

    def __collect_flow_metrics(self, ew, base_url, path, sourcetype, auth_type,
                               username, iname, session_key, input_name, input_item):
        """Poll /flow/metrics/json, emitting one flat event per sample."""
        query = self.metrics_query(input_item)
        request_path = '{}?{}'.format(path, query) if query else path

        try:
            payload = self.__get_request(ew, base_url, request_path, auth_type, username, iname, session_key)
        except Exception as error:
            self._log(ew, EventWriter.ERROR, '{} Error requesting flow metrics: {}'.format(self.pid, error))
            return

        samples = self.flatten_samples(payload)
        if samples is None:
            self._log(ew, EventWriter.ERROR, '{} Could not read the flow metrics response'.format(self.pid))
            return

        for sample in samples:
            ew.write_event(Event(
                sourcetype=sourcetype,
                stanza=input_name,
                data=json.dumps(sample),
                host=input_item.get("host")
            ))

        self._log(ew, EventWriter.INFO, '{} Flow metrics collected: {} samples ({})'.format(
            self.pid, len(samples), request_path))


    def __collect_bulletins(self, ew, base_url, path, sourcetype, auth_type,
                            username, iname, session_key, input_name, input_item):
        """Poll the bulletin board, emitting one event per bulletin.

        Resumes from the highest id seen, so a bulletin is not indexed twice.
        """
        # A bulletin id can legitimately be 0, so test for absence, not truth.
        after = self.__read_checkpoint(ew, input_name, 'bulletin_after')
        request_path = '{}?limit={}'.format(path, self.bulletin_page_limit)
        if after is not None:
            request_path += '&after={}'.format(after)

        try:
            payload = self.__get_request(ew, base_url, request_path, auth_type, username, iname, session_key)
        except Exception as error:
            self._log(ew, EventWriter.ERROR, '{} Error requesting the bulletin board: {}'.format(self.pid, error))
            return

        bulletins = self.bulletins_of(payload)
        if bulletins is None:
            self._log(ew, EventWriter.ERROR, '{} Could not read the bulletin board response'.format(self.pid))
            return

        for entry in bulletins:
            ew.write_event(Event(
                sourcetype=sourcetype,
                stanza=input_name,
                data=json.dumps(entry),
                host=input_item.get("host")
            ))

        highest = self.highest_bulletin_id(bulletins)
        if highest is not None:
            self.__write_checkpoint(ew, input_name, 'bulletin_after', highest)

        self._log(ew, EventWriter.INFO, '{} Bulletins collected: {} (resuming after id {})'.format(
            self.pid, len(bulletins), highest if highest is not None else after))

        if len(bulletins) >= self.bulletin_page_limit:
            self._log(ew, EventWriter.WARN, '{} The bulletin board returned a full page ({}): bulletins may have been dropped before this poll. Shorten the input interval, or use SiteToSiteBulletinReportingTask for guaranteed delivery'.format(
                self.pid, self.bulletin_page_limit))


    def __urljoin(self, *args):
        trailing_slash = '/' if args[-1].endswith('/') else ''
        return str("/".join(map(lambda x: str(x).strip('/'), args)) + trailing_slash)


    def __get_token(self, ew, base_url, user, password):
        req_args = {}
        req_args["headers"] = {'Content-Type': 'application/x-www-form-urlencoded', "charset": "UTF-8"}
        req_args["data"] = {'username': user, 'password': password}
        req_args["verify"] = self.tls_verify

        url = self.__urljoin(base_url, "/access/token")
        self._log(ew, EventWriter.INFO, '{} get_token - url: {}'.format(self.pid, url))
        try:
            response = requests.post(url, **req_args)
            if response.status_code >= 400:
                self._log(ew, EventWriter.ERROR, '{} get_token - Error HTTP token request - status_code: {}, reason: {}, url: {}'.format(self.pid, response.status_code, response.reason, url))
                return None
            self._log(ew, EventWriter.INFO, '{} get_token - OK - status_code: {}, response_elapsed: {}, url: {}'.format(self.pid, response.status_code, response.elapsed.total_seconds(), url))
            return response.text
        except Exception as error:
            self._log(ew, EventWriter.ERROR, '{} Error token request - {}{}'.format(self.pid, error, self.__tls_hint(error)))
            return None


    def __get_request(self, ew, base_url, path, auth_type, username, input_name, session_key):
        """The response body, or None when there is no usable one.

        None on any status >= 400, and on a transport error. It used to return
        `response.text` whatever the status, so an error body was indexed as
        though it were data: a custom endpoint pointed at a path that does not
        exist produced one event per poll containing "The specified resource
        could not be found", under whatever sourcetype the user had chosen,
        with nothing to mark it as a failure. The add-on logged the 404 and
        indexed it anyway (defect CE-1).
        """
        self._log(ew, EventWriter.INFO, '{} Resquest base_url:{} path:{}, auth_type:{}, input_name:{}'.format(self.pid, base_url, path, auth_type, input_name))
        if auth_type == "none":
            url = self.__urljoin(base_url, path)
            
            req_args = {}
            req_args["headers"] = {'Content-Type': 'application/json', 'Accept':'application/json'}
            req_args["timeout"] = 30
            req_args["verify"] = self.tls_verify

            try:
                response = requests.get(url, **req_args)
                if response.status_code >= 400:
                    self._log(ew, EventWriter.ERROR, '{} Error HTTP request - status_code: {}, reason: {}, url: {}'.format(self.pid, response.status_code, response.reason, url))
                    return None
                self._log(ew, EventWriter.INFO, '{} Get OK - status_code: {}, response_elapsed: {}, url: {}'.format(self.pid, response.status_code, response.elapsed.total_seconds(), url))
                return response.text
            except Exception as error:
                self._log(ew, EventWriter.ERROR, '{} Error request - {}{}'.format(self.pid, error, self.__tls_hint(error)))
        else:
            # Only the authenticated path needs the stored password, and only to
            # renew the token. Fetching it unconditionally meant one wasted
            # storage/passwords call per endpoint per cycle in auth_type=none,
            # and an error logged for a credential that mode never stores.
            password = self.__get_password(ew, session_key, input_name, username)
            token = self.__read_token(ew, session_key, input_name)
            if not token:
                # Cold start: nothing stored yet. The input used to send the
                # literal string "unknown" as the bearer, let NiFi answer 401
                # and renew from there. It worked, but it asked to be refused:
                # one ERROR per enabled endpoint on every fresh install, in a
                # log an operator reads to decide whether the add-on is
                # healthy, saying "Error HTTP request - status_code: 401" when
                # nothing was wrong (TA-7). Ask for the token first instead.
                #
                # The 401 branch below stays: it is the other case, a token
                # that was valid and expired, and that one cannot be predicted.
                self._log(ew, EventWriter.INFO, '{} No stored token for input {}; requesting one before the first call'.format(self.pid, input_name))
                token = self.__get_token(ew, base_url, username, password)
                if not token:
                    self._log(ew, EventWriter.ERROR, '{} Could not obtain a token, aborting request - url: {}'.format(self.pid, self.__urljoin(base_url, path)))
                    return None
                self.__write_token(ew, session_key, input_name, token)
            self._log(ew, EventWriter.INFO, '{} Request base_url:{} path:{}, auth_type:{}, username:{}, input_name:{}, token:{}'.format(self.pid, base_url, path, auth_type, username, input_name, self.__redact(token)))
            
            url = self.__urljoin(base_url, path)

            req_args = {}
            req_args["headers"] = {'Content-Type': 'application/json', 'Accept':'application/json', 'Authorization': 'Bearer {}'.format(token)}
            req_args["timeout"] = 30
            req_args["verify"] = self.tls_verify

            try:
                response = requests.get(url, **req_args)
                if response.status_code == 401:
                    self._log(ew, EventWriter.ERROR, '{} Error HTTP request - status_code: {}, reason: {}, url: {}'.format(self.pid, response.status_code, response.reason, url))
                    token = self.__get_token(ew, base_url, username, password)
                    if not token:
                        self._log(ew, EventWriter.ERROR, '{} Token renewal failed, aborting request - url: {}'.format(self.pid, url))
                        return None
                    self.__write_token(ew, session_key, input_name, token)
                    req_args["headers"] = {'Content-Type': 'application/json', 'Accept':'application/json', 'Authorization': 'Bearer {}'.format(token)}
                    response = requests.get(url, **req_args)
                    if response.status_code >= 400:
                        self._log(ew, EventWriter.ERROR, '{} Error HTTP request - status_code: {}, reason: {}, url: {}'.format(self.pid, response.status_code, response.reason, url))
                        return None
                    self._log(ew, EventWriter.INFO, '{} Get OK - status_code: {}, response_elapsed: {}, url: {}'.format(self.pid, response.status_code, response.elapsed.total_seconds(), url))
                    return response.text
                elif response.status_code >= 400:
                    self._log(ew, EventWriter.ERROR, '{} Error HTTP request - status_code: {}, reason: {}, url: {}'.format(self.pid, response.status_code, response.reason, url))
                    return None
                self._log(ew, EventWriter.INFO, '{} Get OK - status_code: {}, response_elapsed: {}, url: {}'.format(self.pid, response.status_code, response.elapsed.total_seconds(), url))
                return response.text
            except Exception as error:
                self._log(ew, EventWriter.ERROR, '{} Error request - {}{}'.format(self.pid, error, self.__tls_hint(error)))


    @staticmethod
    def _event_host(configured, stanza_name):
        """The host the input's events carry.

        The form promises "Used as the host value unless one is set below",
        and nothing implemented it: the configured value was copied as is.
        With no host in the stanza splunkd passes its own placeholder,
        "$decideOnStartup", and that literal became the host of every event --
        which matches no row of the instance lookup, so an input created from
        the form without a Host showed up on no dashboard.
        """
        value = (configured or "").strip()
        if not value or value.startswith("$"):
            return stanza_name
        return value

    @staticmethod
    def _is_mask(value):
        """True for an empty value or one made only of asterisks.

        UCC masks with six, the pre-UCC add-on with eight; neither is a
        password anyone could have.
        """
        value = (value or "").strip()
        return not value or set(value) == {"*"}

    def __get_password(self, ew, session_key, input_name, username):
        """The NiFi password for this input, or None.

        In order of preference:

        1. What the configuration form stored: UCC's realm, keyed by this
           input's stanza name. The normal case.
        2. What the 1.x add-on stored: no realm, keyed by the NiFi username.
           An upgrade that has not re-saved its inputs yet. Keyed by user, so
           two inputs with the same NiFi user but different passwords shared
           one credential -- which is why it is only a fallback.
        3. A cleartext password in inputs.conf, for a stanza written by hand.
           The Inputs page encrypts it the next time it is opened.
        """
        if self.password_cache is not None:
            return self.password_cache

        password = self.__form_password(ew, session_key, input_name)
        if password is None:
            password = self.__legacy_password(ew, session_key, username)
            if password is not None:
                self._log(ew, EventWriter.WARN, '{} Input {} is using the credential the 1.x add-on stored for user {}. Open the input and save it again to store its password per input.'.format(self.pid, input_name, username))
        if password is None and self.inline_password:
            password = self.inline_password
            self._log(ew, EventWriter.WARN, '{} Input {} has its password in cleartext in inputs.conf. Opening Inputs in the add-on encrypts it.'.format(self.pid, input_name))
        if password is None:
            self._log(ew, EventWriter.ERROR, '{} No password found for input {} - it cannot authenticate. Open the input, enter the password and save it.'.format(self.pid, input_name))
            return None

        self.password_cache = password
        return password

    def __form_password(self, ew, session_key, input_name):
        try:
            manager = CredentialManager(session_key, self.app_name, realm=self.ucc_realm)
            stored = manager.get_password(input_name)
        except CredentialNotExistException:
            return None
        except Exception as error:
            self._log(ew, EventWriter.ERROR, '{} Could not read the stored password of input {}: {}'.format(self.pid, input_name, error))
            return None
        try:
            fields = json.loads(stored)
        except ValueError:
            return None
        password = fields.get("password") if isinstance(fields, dict) else None
        return None if self._is_mask(password) else password

    def __legacy_password(self, ew, session_key, username):
        if not username:
            return None
        service = client.connect(token=session_key)
        for storage_password in service.storage_passwords:
            # Only the entries the 1.x add-on wrote: no realm. The token and
            # UCC's credentials live in storage/passwords too, under realms
            # of their own, and an input named like the NiFi user would
            # otherwise match here.
            if storage_password.realm:
                continue
            if storage_password.username == username:
                return storage_password.content.clear_password
        return None
    

if __name__ == "__main__":
    sys.exit(NiFiScript().run(sys.argv))
