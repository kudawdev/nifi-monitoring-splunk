# Tests in Docker compose

## Stand Alone - Nifi 1.19, Splunk 9.0

Run 1 nifi 1.19 container (standalone) and 1 splunk 9.0 container (standalone)

* Edit the .env file to set variables

* Run docker compose test environment
```
docker compose -f nifi119-splunk90-standalone.yml up
```

* In Splunk disable SSL in HEC global configuration (Workaround).

* Configure Nifi following the doc instructions.

## Stand Alone with Login - Nifi 1.19, Splunk 9.0

Run 1 nifi 1.19 container (standalone) and 1 splunk 9.0 container (standalone)

* Edit the .env file to set variables

* Run docker compose test environment
```
docker compose -f nifi119-splunk90-nifi_login.yml up
```

* In Splunk disable SSL in HEC global configuration (Workaround).

* Configure Nifi following the doc instructions.



## Stand Alone - Nifi 1.23, Splunk 9.0

Run 1 nifi 1.23 container (standalone) and 1 splunk 9.0 container (standalone)

* Edit the .env file to set variables

* Run docker compose test environment
```
docker compose -f nifi123-splunk90-standalone.yml up
```

* In Splunk disable SSL in HEC global configuration (Workaround).

* Configure Nifi following the doc instructions.

## Stand Alone with Login - Nifi 1.23, Splunk 9.0

Run 1 nifi 1.23 container (standalone) and 1 splunk 9.0 container (standalone)

* Edit the .env file to set variables

* Run docker compose test environment
```
docker compose -f nifi123-splunk90-nifi_login.yml up
```

* In Splunk disable SSL in HEC global configuration (Workaround).

* Configure Nifi following the doc instructions.
