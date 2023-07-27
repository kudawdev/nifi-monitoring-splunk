import sys
import os
import requests
import urllib3
import dotenv
import xml.etree.ElementTree as ElementTree
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))
import splunklib.client as client
from splunklib.modularinput import EventWriter, Argument, Scheme, Event, Script
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

dotenv_file = dotenv.find_dotenv()
dotenv.load_dotenv(dotenv_file)


class NiFiScript(Script):

    mask = "********"
    endpoints = [
            {"name":"endpoint_flow_status", "sourcetype":"nifi:api:flow_status", "path":"/flow/status"},
            {"name":"endpoint_system_diagnostics", "sourcetype":"nifi:api:system_diagnostics", "path":"/system-diagnostics"},
            {"name":"endpoint_site_to_site", "sourcetype":"nifi:api:site_to_site", "path":"/site-to-site"},
            {"name":"endpoint_processors_history", "sourcetype":"nifi:api:processors_history", "path":"/flow/processors/{id}/status/history"},
            {"name":"endpoint_process_groups_history", "sourcetype":"nifi:api:process_groups_history", "path":"/flow/process-groups/{id}/status/history"}
        ]
    pid = 'Nifi Log pid="{}"'.format(uuid.uuid4())

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
        a = 1
        b = 2
        if a >= b:
            raise ValueError("a >= b")
    

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

        kind, iname = input_name.split("://")

        EventWriter.log(ew, EventWriter.INFO, "{} Started Nifi Get Data for input: input_name:{}, input_item:{}".format(self.pid, input_name, input_item))

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
            
        
        for ep in self.endpoints:
            path = ep.get("path")
            sourcetype = ep.get("sourcetype")
            EventWriter.log(ew, EventWriter.INFO, '{} Request endpoint: {}'.format(self.pid, ep))
            
            if (ep.get('name') == 'endpoint_processors_history') and (processors):
                plist = list(map(lambda v: v.replace('\n',''), filter(lambda u: u != '', processors.replace('\n', ',').split(','))))
                EventWriter.log(ew, EventWriter.INFO, '{} list of plist: {}'.format(self.pid, plist))
                for p in plist:
                    new_path = path.format(id=p.strip())
                    EventWriter.log(ew, EventWriter.INFO, '{} endpoint_processors_history: {}'.format(self.pid, p))
                    try:
                        response = self.__get_request(ew, base_url, new_path, auth_type, username, iname, session_key)
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
            elif input_item.get(ep.get('name')) == '1':                
                try:
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


            if (ep.get('name') == 'endpoint_process_groups_history') and (process_groups):
                plist = list(map(lambda v: v.replace('\n',''), filter(lambda u: u != '', process_groups.replace('\n', ',').split(','))))
                EventWriter.log(ew, EventWriter.INFO, '{} list of plist: {}'.format(self.pid, plist))
                for p in plist:
                    new_path = path.format(id=p.strip())
                    EventWriter.log(ew, EventWriter.INFO, '{} endpoint_process_groups_history: {}'.format(self.pid, p))
                    try:
                        response = self.__get_request(ew, base_url, new_path, auth_type, username, iname, session_key)
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
            elif input_item.get(ep.get('name')) == '1':                
                try:
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

    def __urljoin(self, *args):
        trailing_slash = '/' if args[-1].endswith('/') else ''
        return str("/".join(map(lambda x: str(x).strip('/'), args)) + trailing_slash)


    def __get_token(self, ew, base_url, user, password):
        req_args = {}
        req_args["headers"] = {'Content-Type': 'application/x-www-form-urlencoded', "charset": "UTF-8"}
        req_args["data"] = {'username': user, 'password': password}
        req_args["verify"] = False

        url = self.__urljoin(base_url, "/access/token")
        EventWriter.log(ew, EventWriter.INFO, '{} get_token - url: {}'.format(self.pid, url))
        try:
            response = requests.post(url, **req_args)
            if response.status_code >= 400:
                EventWriter.log(ew, EventWriter.ERROR, '{} get_token - Error HTTP token request - status_code: {}, reason: {}, url: {}'.format(self.pid, response.status_code, response.reason, url))
            else:
                EventWriter.log(ew, EventWriter.INFO, '{} get_token - OK - status_code: {}, response_elapsed: {}, url: {}'.format(self.pid, response.status_code, response.elapsed.total_seconds(), url))
            return response.text
        except Exception as error:
            EventWriter.log(ew, EventWriter.ERROR, '{} Error token request - {}'.format(self.pid, error))


    def __get_request(self, ew, base_url, path, auth_type, username, input_name, session_key):
        password = self.__get_password(ew, session_key, username)

        EventWriter.log(ew, EventWriter.INFO, '{} Resquest base_url:{} path:{}, auth_type:{}, input_name:{}'.format(self.pid, base_url, path, auth_type, input_name))
        if auth_type == "none":
            url = self.__urljoin(base_url, path)
            
            req_args = {}
            req_args["headers"] = {'Content-Type': 'application/json', 'Accept':'application/json'}
            req_args["timeout"] = 30
            req_args["verify"] = False

            try:
                response = requests.get(url, **req_args)
                if response.status_code >= 400:
                    EventWriter.log(ew, EventWriter.ERROR, '{} Error HTTP request - status_code: {}, reason: {}, url: {}'.format(self.pid, response.status_code, response.reason, url))
                else:
                    EventWriter.log(ew, EventWriter.INFO, '{} Get OK - status_code: {}, response_elapsed: {}, url: {}'.format(self.pid, response.status_code, response.elapsed.total_seconds(), url))
                return response.text
            except Exception as error:
                EventWriter.log(ew, EventWriter.ERROR, '{} Error request - {}'.format(self.pid, error))
        else:
            token = os.environ.get(input_name, "unknown")
            EventWriter.log(ew, EventWriter.INFO, '{} Get token base_url:{} path:{}, auth_type:{}, username:{}, password:{}, input_name:{}, token:{}'.format(self.pid, base_url, path, auth_type, username, password, input_name, token))
            
            url = self.__urljoin(base_url, path)

            req_args = {}
            req_args["headers"] = {'Content-Type': 'application/json', 'Accept':'application/json', 'Authorization': 'Bearer {}'.format(token)}
            req_args["timeout"] = 30
            req_args["verify"] = False

            try:
                response = requests.get(url, **req_args)
                if response.status_code == 401:
                    EventWriter.log(ew, EventWriter.ERROR, '{} Error HTTP request - status_code: {}, reason: {}, url: {}'.format(self.pid, response.status_code, response.reason, url))
                    token = self.__get_token(ew, base_url, username, password)
                    dotenv.set_key(dotenv_file, input_name, token)
                    headers = {'Content-Type': 'application/json', 'Accept':'application/json', 'Authorization': 'Bearer {}'.format(token)}
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
                EventWriter.log(ew, EventWriter.ERROR, '{} Error request - {}'.format(self.pid, error))


    def __encrypt_password(self, ew, username, password, session_key):
        EventWriter.log(ew, EventWriter.INFO, '{} Init Encrypt Password'.format(self.pid, ))

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
                                                        'password',
                                                        'interval',
                                                        'endpoint_system_diagnostics',
                                                        'endpoint_flow_status',
                                                        'endpoint_site_to_site',
                                                        'endpoint_processors_history',
                                                        'endpoint_process_groups_history'
                                                        ] if k in input_item)
            item.update(**kwargs).refresh()
           
        except Exception as e:
            raise Exception("Error updating inputs.conf: {}".format(e))
            
    
    def __get_password(self, ew, session_key, username):
        EventWriter.log(ew, EventWriter.INFO, '{} Init Mask Password'.format(self.pid))
        args = {'token': session_key}
        service = client.connect(**args)
        
        # Retrieve the password from the storage/passwords endpoint	
        for storage_password in service.storage_passwords:
            if storage_password.username == username:
                return storage_password.content.clear_password
    

if __name__ == "__main__":
    sys.exit(NiFiScript().run(sys.argv))
