# NIFI Monitoring for Splunk

## Overview

Nifi Monitoring is a solution that proposes to solve a great difficulty encountered
during the development of NIFI Projects and that corresponds to the complex process of monitoring the operation of different NIFI instances simultaneously.

This applications solves this problem centralizing all the information regarding the operation of the different components for various instances and has a set of panels that allow you to clearly and quickly view the operation of these instances.

## Requirements

- Splunk version: 8.2 or higher
- NIFI TA Monitoring

And the following complements:

- [Lookup File Editor](https://splunkbase.splunk.com/app/1724/)
- [Status Indicator - Custom Visualization](https://splunkbase.splunk.com/app/3119/)

## Configuration

This application requieres enabling a HTTP Event Collector (HEC) data input to receive the information from NIFI.

The configuración of NIFI and Splunk allow to establish two types of sending and receiving information depending if the nifi instances have authentication methods.

- No authentication: This setting will set NIFI as the main road for sending data to Splunk.
- Basic authentication: Splunk will be making requests to the NIFI instances to retrieve the information from the Monitoring API by enabling and using the Data Input NIFI.

## Directories

### [nifi_monitoring]
Splunk application that mainly contains the visual features, plus other essential and configuration files for its operation.

### [niti_TA_monitoring]
This technology addon is in charge of processing and indexing the information of the different data sources originating from NIFI servers.

### [template]
this folder contains the template file used in the nifi configuration.

### [docs]
Contains all files to build the documentations.

## Workflows

### dev.yml
Start: Manual. Detail: Executes related validation tasks via AppInspect and unit tests of the Splunk application.

### testing.yml
Start: Automatic (Push branch testing) Detail: Executes tasks related to validation via AppInspect, unit tests.

### main.yml
Start: Automatic (Push branch main) Detail: Executes tasks related to validation via AppInspect, unit tests and generates pre-release packaging for distribution.

### docs.yml
Start: Manual. Detail: Compile docs in mkdocs and publish it.


## Splunkbase Apps

- [Nifi Monitoring for Splunk](https://splunkbase.splunk.com/app/6125)

- [Nifi Monitoring TA](https://splunkbase.splunk.com/app/6124)


## Full documentation
- [NIFI Monitoring for Splunk](https://kudawdev.github.io/nifi-monitoring-splunk/)

## Collaborate
NIFI Monitoring App is hosted in a Github repository where collaboration is always welcome.