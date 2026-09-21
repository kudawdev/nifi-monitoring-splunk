"""Answer "can this add-on reach that NiFi?" before the input is saved.

Getting a NiFi input right means getting four things right at once: the API
URL, whether it speaks HTTP or HTTPS, whether the certificate can be
verified, and whether the credentials work. Without this, all four fail the
same way -- the input saves, and some minutes later an error appears in
splunkd.log, or nothing appears at all. Finding the difference between "the
URL is wrong" and "the password is wrong" meant reading that log.

The handler is deliberately thin: it performs the same two calls the input
performs, in the same order, with the same TLS settings, and reports what
came back. It writes nothing and stores nothing.
"""

import import_declare_test  # noqa: F401  (sets up lib/ on sys.path)

import json
import time

import requests

from splunktaucclib.rest_handler import admin_external, util
from splunktaucclib.rest_handler.admin_external import AdminExternalHandler
from splunktaucclib.rest_handler.endpoint import RestModel, SingleModel, field

util.remove_http_proxy_env_vars()

TIMEOUT = 15


def _join(base_url, path):
    """The same join the input uses: keep the base path, append the endpoint.

    urljoin would discard '/nifi-api' from 'http://host:8080/nifi-api' when
    given an absolute path, which is the single most common way to configure
    a NiFi URL. Defect B-4 was exactly this.
    """
    return "%s/%s" % (base_url.rstrip("/"), path.lstrip("/"))


class TestConnectionHandler(AdminExternalHandler):
    """POST /servicesNS/-/nifi_TA_monitoring/nifi_test_connection"""

    def handleList(self, confInfo):
        raise NotImplementedError("test_connection only answers to create")

    def handleEdit(self, confInfo):
        raise NotImplementedError("test_connection only answers to create")

    def handleRemove(self, confInfo):
        raise NotImplementedError("test_connection only answers to create")

    def handleCreate(self, confInfo):
        self.confInfo = confInfo
        data = self.callerArgs.data
        api_url = self._one(data, "api_url").rstrip("/")
        auth_type = self._one(data, "auth_type") or "none"
        username = self._one(data, "username")
        password = self._one(data, "password")
        verify = self._flag(self._one(data, "verify_tls"), default=True)
        ca_bundle = self._one(data, "ca_bundle")

        if not api_url:
            self._fail("Enter the NiFi API URL first.")
            return

        verify_arg = ca_bundle if (verify and ca_bundle) else verify
        started = time.time()
        try:
            token = None
            if auth_type == "basic":
                token = self._login(api_url, username, password, verify_arg)
                if isinstance(token, dict):          # a failure, already shaped
                    self._reply(token)
                    return
            self._reply(self._probe(api_url, token, verify_arg, started))
        except requests.exceptions.SSLError as error:
            self._fail(
                "The NiFi certificate could not be verified: %s. Point CA "
                "bundle path at a bundle that trusts it, or turn off Verify "
                "the TLS certificate if you accept an unverified connection."
                % error)
        except requests.exceptions.ConnectionError:
            self._fail(
                "Could not reach %s. Check the host, the port and that Splunk "
                "is allowed to open the connection." % api_url)
        except requests.exceptions.Timeout:
            self._fail(
                "No answer within %d seconds." % TIMEOUT)
        except Exception as error:                   # last resort, still useful
            self._fail(str(error))

    # -- the two calls the input makes ------------------------------------

    def _login(self, api_url, username, password, verify):
        if not username or not password:
            return self._as_dict(False, "basic authentication needs a username "
                                        "and a password.")
        response = requests.post(
            _join(api_url, "/access/token"),
            data={"username": username, "password": password},
            timeout=TIMEOUT, verify=verify)
        if response.status_code == 400 or response.status_code == 401:
            return self._as_dict(False, "NiFi rejected the credentials (HTTP "
                                        "%d)." % response.status_code)
        if response.status_code >= 400:
            return self._as_dict(
                False, "POST /access/token answered HTTP %d. On an "
                       "unauthenticated NiFi choose Authentication: None."
                       % response.status_code)
        return response.text

    def _probe(self, api_url, token, verify, started):
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = "Bearer %s" % token
        response = requests.get(
            _join(api_url, "/system-diagnostics"),
            headers=headers, timeout=TIMEOUT, verify=verify)
        elapsed = int((time.time() - started) * 1000)

        if response.status_code == 401:
            return self._as_dict(
                False, "NiFi answered 401. This instance requires "
                       "authentication: choose Username and password.")
        if response.status_code == 421:
            return self._as_dict(
                False, "NiFi answered 421 Misdirected Request, which means it "
                       "does not recognise the host name in the URL. Set "
                       "nifi.web.proxy.host on the NiFi side.")
        if response.status_code >= 400:
            return self._as_dict(
                False, "GET /system-diagnostics answered HTTP %d."
                       % response.status_code)

        version = self._version_of(response.text)
        return self._as_dict(
            True,
            "Connected to NiFi %s in %d ms." % (version, elapsed)
            if version else "Connected in %d ms, but the response did not "
                            "carry a version." % elapsed)

    @staticmethod
    def _version_of(payload):
        try:
            body = json.loads(payload)
        except ValueError:
            return None
        diagnostics = body.get("systemDiagnostics") or {}
        aggregate = diagnostics.get("aggregateSnapshot") or {}
        info = aggregate.get("versionInfo") or body.get("versionInfo") or {}
        return info.get("niFiVersion")

    # -- shaping ----------------------------------------------------------

    @staticmethod
    def _as_dict(ok, message):
        return {"success": ok, "message": message}

    def _reply(self, payload):
        """ConfigInfo is two levels deep: a stanza, then its keys.

        Assigning a bare string to confInfo["result"] raises
        BadProgrammerException from inside splunkd, whose message quotes the
        JSON it could not place -- so the answer is visible in the error and
        the caller still gets a 500.
        """
        self.confInfo["nifi_test_connection"]["result"] = json.dumps(payload)

    def _fail(self, message):
        self._reply(self._as_dict(False, message))

    @staticmethod
    def _one(data, key):
        """callerArgs.data holds a list per key; take the first, always a str."""
        value = data.get(key)
        if isinstance(value, (list, tuple)):
            value = value[0] if value else ""
        return (value or "").strip()

    @staticmethod
    def _flag(value, default=False):
        if value is None or value == "":
            return default
        return str(value).strip().lower() in ("1", "true", "yes", "on")


# The handler answers from these and writes nothing, but splunktaucclib
# rejects any argument the model does not declare, so they have to be here.
# None is required: a test with a field missing has to produce the message
# that says which one, not a 400 from the framework.
endpoint = SingleModel(
    "nifi_test_connection",
    RestModel(
        fields=[
            field.RestField("api_url", required=False, encrypted=False,
                            default=None, validator=None),
            field.RestField("auth_type", required=False, encrypted=False,
                            default="none", validator=None),
            field.RestField("username", required=False, encrypted=False,
                            default=None, validator=None),
            field.RestField("password", required=False, encrypted=True,
                            default=None, validator=None),
            field.RestField("verify_tls", required=False, encrypted=False,
                            default="1", validator=None),
            field.RestField("ca_bundle", required=False, encrypted=False,
                            default=None, validator=None),
        ],
        name=None,
    ),
    config_name="test_connection",
    need_reload=False,
)


if __name__ == "__main__":
    admin_external.handle(endpoint, handler=TestConnectionHandler)
