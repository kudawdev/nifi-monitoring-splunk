# Tests in Docker compose


## Stand Alone without Login - Nifi 1.23, Splunk 9.1

Run 1 nifi 1.23 container (standalone) and 1 splunk 9.1 container (standalone)

* Run docker compose test environment
```
docker compose -f nifi123-splunk91-nifi_nologin.yml -p "nifi_nologin" up
```

* Connect to splunk container and run the script
```
docker exec -u root -ti $(docker ps -qf "name=nifi_nologin-splunk1") bash
cd /tmp/test/tests/script/
bash init_splunk_nologin.sh (--copy-apps | --config | --all)
```

* In Splunk disable SSL in HEC global configuration (Workaround).


* Connect to nifi container and run the script
```
docker exec -u root -ti $(docker ps -qf "name=nifi_nologin-nifi1") bash
```

* Configure Nifi following the doc instructions.
    - nifi_api_url: http://nifi1:8080/nifi-api/
    - nifi_path: /opt/nifi/nifi-current/
    - process_groups_list (optional)
    - processors_listNiFiMonitoring (optional)
    - splunk_hec: http://splunk1:8088
    - splunk_hec_token: Password123


## Stand Alone with Login - Nifi 1.23, Splunk 9.1

Run 1 nifi 1.23 container (standalone) and 1 splunk 9.1 container (standalone)

* Run docker compose test environment
```
docker compose -f nifi123-splunk91-nifi_login.yml -p "nifi_login" up
```

* In Splunk disable SSL in HEC global configuration (Workaround).

* Configure Nifi following the doc instructions.
