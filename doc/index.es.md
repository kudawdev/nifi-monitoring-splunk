# Introducción

**Nifi Monitoring** centraliza en Splunk la visibilidad operativa de tus
instancias de Apache NiFi — una sola, varias independientes, o en
cluster. En un solo lugar tienes:

- **Estado del flujo**: procesadores corriendo, detenidos o inválidos, y
  datos en cola.
- **Diagnóstico del sistema**: heap, threads y uso de disco por
  repositorio, por nodo.
- **Bulletins**: los errores y advertencias que genera NiFi, con
  trazabilidad de qué componente los produjo.
- **Logs de NiFi** (opcional, vía Universal Forwarder): app, bootstrap,
  usuario y accesos HTTP, buscables sin entrar por terminal a cada host.
- **Métricas de flujo** (opcional): throughput y detalle por componente.
- **Visibilidad de cluster**: rol y heap de cada nodo, sin entrar a cada
  uno por separado.

Los datos llegan de dos formas posibles: Splunk consultando la API de
NiFi (**pull**, la recomendada), o NiFi enviando directo al HEC de Splunk
(**push**, para cuando Splunk no puede alcanzar a NiFi). Ver
[Compatibilidad y estrategia de recolección](compatibility.es.md) para
elegir cuál te corresponde.

Se distribuye como dos apps:

- **Nifi Monitoring** — los dashboards (esta guía).
- **Nifi Monitoring TA** — el add-on que trae los datos de NiFi a Splunk.

![image](/nifi-monitoring-splunk/assets/images/splunk/nifi_home.png)

## Dependencias

- [Lookup File Editor](https://splunkbase.splunk.com/app/1724/), para editar el inventario de instancias.

Siguiente: [Compatibilidad y estrategia de recolección](compatibility.es.md)
— la primera decisión antes de instalar nada.

## Soporte

Gratuito y de código abierto — [contribuye o reporta issues en GitHub](https://github.com/kudawdev/nifi-monitoring-splunk), o escribe a splunk.app@kudaw.com para una evaluación.
