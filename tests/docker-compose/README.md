# Tests in Docker compose

## Stand Alone - Nifi 1.19, Splunk 9.0

Run 1 nifi 1.19 container (standalone) and 1 splunk 9.0 container (standalone)

* Edit the .env file to set variables

* Create a network
```
docker network create --driver overlay nifi_network
```

* Run docker compose test environment
```
docker-compose -f nifi119-splunk90-standalone.yml up
```

* Configure Nifi folloowing the doc instruction

* In Splunk disable SSL in HEC global configuration (Workaround)
