import sys
import os
import re
import requests
import urllib3
import dotenv
#import xml.etree.ElementTree as ElementTree
import uuid
import unicodedata
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))
import splunklib.client as client
from splunklib.modularinput import EventWriter, Argument, Scheme, Event, Script

if dotenv.find_dotenv() == '':
    with open(os.path.join(os.path.dirname(__file__), ".env"), 'w'):
        pass

dotenv_file = dotenv.find_dotenv()
dotenv.load_dotenv(dotenv_file)

class NiFiScript(Script):

    mask = "********"
    endpoints = [
            {"name":"endpoint_flow_status", "sourcetype":"nifi:api:flow_status", "path":"/flow/status"},
            {"name":"endpoint_system_diagnostics", "sourcetype":"nifi:api:system_diagnostics", "path":"/system-diagnostics"},
            {"name":"endpoint_site_to_site", "sourcetype":"nifi:api:site_to_site", "path":"/site-to-site"},
            {"name":"endpoint_processors_history", "sourcetype":"nifi:api:processors_history", "path":"/flow/processors/{id}/status/history"},
            {"name":"endpoint_process_groups_history", "sourcetype":"nifi:api:process_groups_history", "path":"/flow/process-groups/{id}/status/history"},
            {"name":"endpoint_bulletin_board", "sourcetype":"nifi:api:bulletin_board", "path":"/flow/bulletin-board"}
        ]
    pid = 'Nifi Log pid="{}"'.format(uuid.uuid4())
    tls_verify = True
    nifi_version = None

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
            EventWriter.log(ew, EventWriter.WARN, '{} Could not read checkpoint {}: {}'.format(self.pid, name, error))
            return None

    def __write_checkpoint(self, ew, input_name, name, value):
        path = self.__checkpoint_path(input_name, name)
        if not path:
            return
        try:
            with open(path, 'w') as handle:
                handle.write(str(value))
        except Exception as error:
            EventWriter.log(ew, EventWriter.WARN, '{} Could not write checkpoint {}: {}'.format(self.pid, name, error))

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
        EventWriter.log(ew, EventWriter.INFO, '{} Skipping {}: requires NiFi {} and this instance is older'.format(
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

        endpoint_site_to_site_argument = Argument(
            name="endpoint_site_to_site",
            description="Site to Site",
            title="Site to Site",
            data_type=Argument.data_type_boolean,
            required_on_edit=True,
            required_on_create=True
        )
        scheme.add_argument(endpoint_site_to_site_argument)

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
    

    def stream_events(self, inputs, ew):

        EventWriter.log(ew, EventWriter.INFO, '{} Started Stream Events'.format(self.pid))
        
        input_name, input_item = inputs.inputs.popitem()
        
        session_key = self._input_definition.metadata['session_key']
        
        base_url   = input_item.get("api_url")
        auth_type  = input_item.get("auth_type")
        username   = input_item.get("username", None)
        password   = input_item.get("password", None)
        processors = input_item.get("endpoint_processors_history", None)
        process_groups = input_item.get("endpoint_process_groups_history", None)

        self.tls_verify = self._tls_verify(input_item)
        if self.tls_verify is False:
            # Only silence the warning the user has explicitly accepted.
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            EventWriter.log(ew, EventWriter.WARN, '{} TLS certificate verification is DISABLED for this input: credentials and the bearer token can be read by anyone able to intercept the connection'.format(self.pid))

        kind, iname = input_name.split("://")

        EventWriter.log(ew, EventWriter.INFO, "{} Started Nifi Get Data for input: input_name:{}, input_item:{}".format(self.pid, input_name, self.__safe_item(input_item)))

        if auth_type == 'basic':
            try:
                if password != self.mask:
                    EventWriter.log(ew, EventWriter.INFO, '{} Encrypting/Mask password'.format(self.pid))
                    self.__encrypt_password(ew, username, password, session_key)
                    self.__mask_password(ew, session_key, input_name, input_item)
                else:
                    EventWriter.log(ew, EventWriter.INFO, '{} No Encrypting/Mask password'.format(self.pid))
            except Exception as e:
                EventWriter.log(ew, EventWriter.ERROR,'{} There was an error when encrypting/masking the password: {}'.format(self.pid, e))
            
        
        # Detect the NiFi version before deciding what to collect. The response
        # is kept so the system_diagnostics endpoint, when enabled, does not
        # have to be fetched twice.
        diagnostics = self.__get_request(ew, base_url, "/system-diagnostics", auth_type, username, iname, session_key)
        version_info = self.version_info_of(diagnostics)
        self.nifi_version = self.parse_version((version_info or {}).get('niFiVersion'))

        if self.nifi_version:
            EventWriter.log(ew, EventWriter.INFO, '{} Detected NiFi {} (Java {})'.format(
                self.pid, version_info.get('niFiVersion'), version_info.get('javaVersion')))
            ew.write_event(Event(
                sourcetype="nifi:api:version_info",
                stanza=input_name,
                data=json.dumps(version_info),
                host=input_item.get("host")
            ))
        else:
            EventWriter.log(ew, EventWriter.WARN, '{} Could not detect the NiFi version from /system-diagnostics; version-dependent endpoints will be skipped'.format(self.pid))

        for ep in self.endpoints:
            if not self.__supported(ep, ew):
                continue
            path = ep.get("path")
            sourcetype = ep.get("sourcetype")
            EventWriter.log(ew, EventWriter.INFO, '{} Request endpoint: {}'.format(self.pid, ep))
            
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
                    EventWriter.log(ew, EventWriter.DEBUG, '{} Response: {}'.format(self.pid, response))
                    event = Event(
                        sourcetype=sourcetype,
                        stanza=input_name,
                        data=response,
                        host=input_item.get("host")
                    )
                    ew.write_event(event)
                except Exception as e:
                    EventWriter.log(ew, EventWriter.ERROR, '{} There was an error when request: {}'.format(self.pid, e))
            
            elif (ep.get('name') == 'endpoint_processors_history') and (processors):
                plist = self._split_ids(processors)
                EventWriter.log(ew, EventWriter.INFO, '{} list of plist: {}'.format(self.pid, plist))
                for p in plist:
                    new_path = path.format(id=p)
                    EventWriter.log(ew, EventWriter.INFO, '{} endpoint_processors_history: {}'.format(self.pid, p))
                    try:
                        response = self.__get_request(ew, base_url, new_path, auth_type, username, iname, session_key)
                        EventWriter.log(ew, EventWriter.DEBUG, '{} Response: {}'.format(self.pid, response))
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
                        EventWriter.log(ew, EventWriter.ERROR, '{} There was an error when request: {}'.format(self.pid, e))

            elif (ep.get('name') == 'endpoint_process_groups_history') and (process_groups):
                plist = self._split_ids(process_groups)
                EventWriter.log(ew, EventWriter.INFO, '{} list of plist: {}'.format(self.pid, plist))
                for p in plist:
                    new_path = path.format(id=p)
                    EventWriter.log(ew, EventWriter.INFO, '{} endpoint_process_groups_history: {}'.format(self.pid, p))
                    try:
                        response = self.__get_request(ew, base_url, new_path, auth_type, username, iname, session_key)
                        EventWriter.log(ew, EventWriter.DEBUG, '{} Response: {}'.format(self.pid, response))
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
                        EventWriter.log(ew, EventWriter.ERROR, '{} There was an error when request: {}'.format(self.pid, e))
                        
            else:
                EventWriter.log(ew, EventWriter.INFO, 'there wasnt an endpoint detected: ')
                pass

    def __collect_bulletins(self, ew, base_url, path, sourcetype, auth_type,
                            username, iname, session_key, input_name, input_item):
        """Poll the bulletin board, emitting one event per bulletin.

        Resumes from the highest id seen, so a bulletin is not indexed twice.
        """
        after = self.__read_checkpoint(ew, input_name, 'bulletin_after')
        request_path = '{}?limit={}'.format(path, self.bulletin_page_limit)
        if after:
            request_path += '&after={}'.format(after)

        try:
            payload = self.__get_request(ew, base_url, request_path, auth_type, username, iname, session_key)
        except Exception as error:
            EventWriter.log(ew, EventWriter.ERROR, '{} Error requesting the bulletin board: {}'.format(self.pid, error))
            return

        bulletins = self.bulletins_of(payload)
        if bulletins is None:
            EventWriter.log(ew, EventWriter.ERROR, '{} Could not read the bulletin board response'.format(self.pid))
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

        EventWriter.log(ew, EventWriter.INFO, '{} Bulletins collected: {} (resuming after id {})'.format(
            self.pid, len(bulletins), highest if highest is not None else after))

        if len(bulletins) >= self.bulletin_page_limit:
            EventWriter.log(ew, EventWriter.WARN, '{} The bulletin board returned a full page ({}): bulletins may have been dropped before this poll. Shorten the input interval, or use SiteToSiteBulletinReportingTask for guaranteed delivery'.format(
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
        EventWriter.log(ew, EventWriter.INFO, '{} get_token - url: {}'.format(self.pid, url))
        try:
            response = requests.post(url, **req_args)
            if response.status_code >= 400:
                EventWriter.log(ew, EventWriter.ERROR, '{} get_token - Error HTTP token request - status_code: {}, reason: {}, url: {}'.format(self.pid, response.status_code, response.reason, url))
                return None
            EventWriter.log(ew, EventWriter.INFO, '{} get_token - OK - status_code: {}, response_elapsed: {}, url: {}'.format(self.pid, response.status_code, response.elapsed.total_seconds(), url))
            return response.text
        except Exception as error:
            EventWriter.log(ew, EventWriter.ERROR, '{} Error token request - {}{}'.format(self.pid, error, self.__tls_hint(error)))
            return None


    def __get_request(self, ew, base_url, path, auth_type, username, input_name, session_key):
        EventWriter.log(ew, EventWriter.INFO, '{} Resquest base_url:{} path:{}, auth_type:{}, input_name:{}'.format(self.pid, base_url, path, auth_type, input_name))
        if auth_type == "none":
            url = self.__urljoin(base_url, path)
            
            req_args = {}
            req_args["headers"] = {'Content-Type': 'application/json', 'Accept':'application/json'}
            req_args["timeout"] = 30
            req_args["verify"] = self.tls_verify

            try:
                response = requests.get(url, **req_args)
                if response.status_code >= 400:
                    EventWriter.log(ew, EventWriter.ERROR, '{} Error HTTP request - status_code: {}, reason: {}, url: {}'.format(self.pid, response.status_code, response.reason, url))
                else:
                    EventWriter.log(ew, EventWriter.INFO, '{} Get OK - status_code: {}, response_elapsed: {}, url: {}'.format(self.pid, response.status_code, response.elapsed.total_seconds(), url))
                return response.text
            except Exception as error:
                EventWriter.log(ew, EventWriter.ERROR, '{} Error request - {}{}'.format(self.pid, error, self.__tls_hint(error)))
        else:
            # Only the authenticated path needs the stored password, and only to
            # renew the token. Fetching it unconditionally meant one wasted
            # storage/passwords call per endpoint per cycle in auth_type=none,
            # and an error logged for a credential that mode never stores.
            password = self.__get_password(ew, session_key, username)
            dotenv.load_dotenv(dotenv_file)
            token = os.environ.get(unicodedata.normalize('NFKD',input_name).replace(' ',''), "unknown")
            EventWriter.log(ew, EventWriter.INFO, '{} Request base_url:{} path:{}, auth_type:{}, username:{}, input_name:{}, token:{}'.format(self.pid, base_url, path, auth_type, username, input_name, self.__redact(token)))
            
            url = self.__urljoin(base_url, path)

            req_args = {}
            req_args["headers"] = {'Content-Type': 'application/json', 'Accept':'application/json', 'Authorization': 'Bearer {}'.format(token)}
            req_args["timeout"] = 30
            req_args["verify"] = self.tls_verify

            try:
                response = requests.get(url, **req_args)
                if response.status_code == 401:
                    EventWriter.log(ew, EventWriter.ERROR, '{} Error HTTP request - status_code: {}, reason: {}, url: {}'.format(self.pid, response.status_code, response.reason, url))
                    token = self.__get_token(ew, base_url, username, password)
                    if not token:
                        EventWriter.log(ew, EventWriter.ERROR, '{} Token renewal failed, aborting request - url: {}'.format(self.pid, url))
                        return None
                    dotenv.set_key(dotenv_file, unicodedata.normalize('NFKD',input_name).replace(' ',''), token)
                    req_args["headers"] = {'Content-Type': 'application/json', 'Accept':'application/json', 'Authorization': 'Bearer {}'.format(token)}
                    response = requests.get(url, **req_args)
                    if response.status_code >= 400:
                        EventWriter.log(ew, EventWriter.ERROR, '{} Error HTTP request - status_code: {}, reason: {}, url: {}'.format(self.pid, response.status_code, response.reason, url))
                    else:
                        EventWriter.log(ew, EventWriter.INFO, '{} Get OK - status_code: {}, response_elapsed: {}, url: {}'.format(self.pid, response.status_code, response.elapsed.total_seconds(), url))
                    return response.text
                elif response.status_code >= 400:
                    EventWriter.log(ew, EventWriter.ERROR, '{} Error HTTP request - status_code: {}, reason: {}, url: {}'.format(self.pid, response.status_code, response.reason, url))
                else:
                    EventWriter.log(ew, EventWriter.INFO, '{} Get OK - status_code: {}, response_elapsed: {}, url: {}'.format(self.pid, response.status_code, response.elapsed.total_seconds(), url))
                return response.text
            except Exception as error:
                EventWriter.log(ew, EventWriter.ERROR, '{} Error request - {}{}'.format(self.pid, error, self.__tls_hint(error)))


    def __encrypt_password(self, ew, username, password, session_key):
        EventWriter.log(ew, EventWriter.INFO, '{} Init Encrypt Password'.format(self.pid))

        args = {'token': session_key}
        service = client.connect(**args)
      
        try:
            for storage_password in service.storage_passwords:
                if storage_password.username == username:
                    service.storage_passwords.delete(username=storage_password.username)
                    break
 
            service.storage_passwords.create(password, username)
 
        except Exception as e:
            EventWriter.log(ew, EventWriter.INFO, '{} An error occurred updating credentials. Please ensure your user account has admin_all_objects and/or list_storage_passwords capabilities. Details: {}'.format(self.pid, e))
            raise Exception("An error occurred updating credentials. Please ensure your user account has admin_all_objects and/or list_storage_passwords capabilities. Details: {}".format(e))


    def __mask_password(self, ew, session_key, input_name, input_item):
        EventWriter.log(ew, EventWriter.INFO, '{} Init Mask Password'.format(self.pid))

        kind, name = input_name.split("://")

        try:
            args = {'token': session_key}
            service = client.connect(**args)
            item = service.inputs.__getitem__((name, kind))

            kwargs = dict((k, input_item[k]) for k in ['username', 
                                                        'api_url',
                                                        'auth_type',
                                                        'interval',
                                                        'endpoint_system_diagnostics',
                                                        'endpoint_flow_status',
                                                        'endpoint_site_to_site',
                                                        'endpoint_processors_history',
                                                        'endpoint_process_groups_history'
                                                        ] if k in input_item)
            kwargs['password'] = self.mask
            item.update(**kwargs).refresh()
           
        except Exception as e:
            raise Exception("Error updating inputs.conf: {}".format(e))
            
    
    def __get_password(self, ew, session_key, username):
        EventWriter.log(ew, EventWriter.INFO, '{} Retrieving stored credential'.format(self.pid))
        args = {'token': session_key}
        service = client.connect(**args)
        
        # Retrieve the password from the storage/passwords endpoint 
        for storage_password in service.storage_passwords:
            if storage_password.username == username:
                return storage_password.content.clear_password

        EventWriter.log(ew, EventWriter.ERROR, '{} No stored credential found for user {} - the input cannot authenticate. Re-save the input to store the password.'.format(self.pid, username))
        return None
    

if __name__ == "__main__":
    sys.exit(NiFiScript().run(sys.argv))
