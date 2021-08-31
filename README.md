# NIFI Monitoring for Splunk

## Objetivo
Nifi Monitoring es una propuesta que centraliza la información sobre el funcionamiento de los dintintos componentes para varias instancias simultaneamente, además dispone de una serie de paneles que permiten visualizar de manera rápida y clara el funcionamiento de estas instancias.

## Directorios

### [nifi_monitoring]
Aplicación de Splunk que contiene principalmente las caracteristicas visuales, además de otros archivos escenciales y de configuración para su funcionamiento.

### [niti_TA_monitoring]
Este complemento es encargado de procesar e indexar la información de las distintas fuentes de datos originadas desde servidores NIFI.



## Workflows

### dev.yml
Inicio: Automático (Push branch developer) Detalle: Ejecuta tareas relacionadas de validación vía AppInspect y pruebas unitarias de la aplicación de Splunk.

### main.yml
Inicio: Automático (Push branch testing) Detalle: Ejecuta tareas relacionadas a validación vía AppInspect, pruebas unitarias y genera el empaquetado pre-release para su distribución.