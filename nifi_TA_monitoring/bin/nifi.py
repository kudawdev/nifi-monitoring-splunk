import sys
import os
import json
import requests
import urllib3
import dotenv
from splunklib.modularinput import *
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

dotenv_file = dotenv.find_dotenv()
dotenv.load_dotenv(dotenv_file)

class NiFiScript(Script):


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
        
        return scheme


    def validate_input(self, validation_definition):
        pass


    def urljoin(self, *args):
        trailing_slash = '/' if args[-1].endswith('/') else ''
        return str("/".join(map(lambda x: str(x).strip('/'), args)) + trailing_slash)


    def get_token(self, ew, base_url, user, password):
        headers = {'Content-Type': 'application/x-www-form-urlencoded', "charset": "UTF-8"}
        data = {'username': user, 'password': password}
        url = self.urljoin(base_url, "/access/token")
        EventWriter.log(ew, EventWriter.INFO, 'get_token - url: {}'.format(url))
        try:
            response = requests.post(url, headers=headers, data=data, timeout=30, verify=False)
            if response.status_code >= 400:
                EventWriter.log(ew, EventWriter.ERROR, 'get_token - Error HTTP token request - status_code: {}, reason: {}, url: {}'.format(response.status_code, response.reason, url))
            else:
                EventWriter.log(ew, EventWriter.INFO, 'get_token - OK - status_code: {}, response_elapsed: {}, url: {}'.format(response.status_code, response.elapsed.total_seconds(), url))
            return response.text
        except Exception as error:
            EventWriter.log(ew, EventWriter.ERROR, 'Error token request - {}'.format(error))


    def get_request(self, ew, base_url, path, auth_type, username, password, input_name):
        EventWriter.log(ew, EventWriter.INFO, 'Resquest base_url:{} path:{}, auth_type:{}, input_name:{}'.format(base_url, path, auth_type, input_name))
        if auth_type == "none":
            headers = {'Content-Type': 'application/json', 'Accept':'application/json'}
            url = self.urljoin(base_url, path)
            try:
                response = requests.get(url, headers=headers, timeout=30, verify=False)
                if response.status_code >= 400:
                    EventWriter.log(ew, EventWriter.ERROR, 'Error HTTP request - status_code: {}, reason: {}, url: {}'.format(response.status_code, response.reason, url))
                else:
                    EventWriter.log(ew, EventWriter.INFO, 'Get OK - status_code: {}, response_elapsed: {}, url: {}'.format(response.status_code, response.elapsed.total_seconds(), url))
                return response.text
            except Exception as error:
                EventWriter.log(ew, EventWriter.ERROR, 'Error request - {}'.format(error))
        else:
            token = os.environ.get(input_name, "unknown")
            EventWriter.log(ew, EventWriter.INFO, 'obteniendo token base_url:{} path:{}, auth_type:{}, username:{}, password:{}, input_name:{}, token:{}'.format(base_url, path, auth_type, username, password, input_name, token))
            headers = {'Content-Type': 'application/json', 'Accept':'application/json', 'Authorization': 'Bearer {}'.format(token)}
            url = self.urljoin(base_url, path)
            try:
                response = requests.get(url, headers=headers, timeout=30, verify=False)
                if response.status_code == 401:
                    EventWriter.log(ew, EventWriter.ERROR, 'Error HTTP request - status_code: {}, reason: {}, url: {}'.format(response.status_code, response.reason, url))
                    token = self.get_token(ew, base_url, username, password)
                    dotenv.set_key(dotenv_file, input_name, token)
                    headers = {'Content-Type': 'application/json', 'Accept':'application/json', 'Authorization': 'Bearer {}'.format(token)}
                    response = requests.get(url, headers=headers, timeout=30, verify=False)
                    if response.status_code >= 400:
                        EventWriter.log(ew, EventWriter.ERROR, 'Error HTTP request - status_code: {}, reason: {}, url: {}'.format(response.status_code, response.reason, url))
                    else:
                        EventWriter.log(ew, EventWriter.INFO, 'Get OK - status_code: {}, response_elapsed: {}, url: {}'.format(response.status_code, response.elapsed.total_seconds(), url))
                    return response.text
                elif response.status_code >= 400:
                    EventWriter.log(ew, EventWriter.ERROR, 'Error HTTP request - status_code: {}, reason: {}, url: {}'.format(response.status_code, response.reason, url))
                else:
                    EventWriter.log(ew, EventWriter.INFO, 'Get OK - status_code: {}, response_elapsed: {}, url: {}'.format(response.status_code, response.elapsed.total_seconds(), url))
                return response.text
            except Exception as error:
                EventWriter.log(ew, EventWriter.ERROR, 'Error request - {}'.format(error))

    

    def stream_events(self, inputs, ew):
        endpoints = [
            {"sourcetype":"nifi:api:flow_status", "path":"/flow/status"},
            {"sourcetype":"nifi:api:system_diagnostics", "path":"/system-diagnostics"},
            {"sourcetype":"nifi:api:site_to_site", "path":"/site-to-site"},
            {"sourcetype":"nifi:api:controller_cluster", "path":"/controller/cluster"},
        ]

        #for input_name, input_item in inputs.inputs.iteritems():
        input_name, input_item = inputs.inputs.popitem()
        base_url = input_item.get("api_url")
        auth_type = input_item.get("auth_type")
        username = input_item.get("username", None)
        password = input_item.get("password", None)

        kind, iname = input_name.split("://")

        EventWriter.log(ew, EventWriter.INFO, "Started Nifi Get Data for input: {}".format(input_name))

        for ep in endpoints:
            path = ep.get("path")
            sourcetype = ep.get("sourcetype")
            response = self.get_request(ew, base_url, path, auth_type, username, password, iname)
            
            event = Event(
                sourcetype=sourcetype,
                stanza=input_name,
                data=response,
                host=input_item.get("host")
            )
            ew.write_event(event)


if __name__ == "__main__":
    sys.exit(NiFiScript().run(sys.argv))
