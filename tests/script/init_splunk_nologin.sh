#!/bin/bash
copy_apps() {
    echo "Copy apps nifi_monitoring, nifi_TA_monitoring"
    sudo -u splunk cp -r /tmp/test/nifi_monitoring /opt/splunk/etc/apps/
    sudo -u splunk cp -r /tmp/test/nifi_TA_monitoring /opt/splunk/etc/apps/
    echo "Copy apps completed"
}

config() {
    echo "Copy conf"
    sudo -u splunk mkdir -p /opt/splunk/etc/apps/nifi_monitoring/local/
    sudo -u splunk cp -r /tmp/test/tests/conf/inputs_nologin.conf /opt/splunk/etc/apps/nifi_monitoring/local/inputs.conf

    sudo -u splunk cp -r /tmp/test/tests/lookups/nifi.csv /opt/splunk/var/run/splunk/csv/

    sudo -u splunk /opt/splunk/bin/splunk search "| inputcsv nifi.csv | outputlookup instance" -app nifi_monitoring -auth admin:Password123

    echo "Copy conf completed"
}


restart_splunk(){
    echo "Restart splunk"
    sudo -u splunk /opt/splunk/bin/splunk restart
    echo "Restart completed"
}


case "$1" in
  "--copy-apps")
    copy_apps
    ;;
  "--config")
    config
    ;;
  "--all")
    copy_apps
    config
    restart_splunk
    ;;
  *)
    echo "Options: --copy-apps | --config | --all"
    exit 1
    ;;
esac