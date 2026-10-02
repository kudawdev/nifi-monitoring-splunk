---
title: Estrategia pull (1.2)
---

# Estrategia pull: Splunk Data Input NiFi (1.2)

!!! note "Para la versión 1.2.x de las dos apps"
    Esta es la configuración tal como era en la release 1.2.3. En la 2.0 el
    input tiene su propio formulario dentro de la TA — ver
    [Estrategia pull (2.0)](config-nifi-monitoring-2-0.es.md).

*Esta configuración debe aplicarse cuando las instancias de NiFi cuentan
con al menos autenticación básica.*

En los data inputs de Splunk puedes configurar varios recursos, como: NiFi
Endpoints para el monitoreo de System Diagnostics, Flow Status y Site to
Site, y el NiFi Status History para el monitoreo específico de procesadores
y grupos de procesos según sus ID.

Para configurar, en el Splunk donde está instalada la aplicación Nifi
Monitoring, abre el Home de la app.

![image](/nifi-monitoring-splunk/assets/images/splunk/nifi_home.png)

Luego ve a **Settings > Data Inputs**.

![image](/nifi-monitoring-splunk/assets/images/splunk/data_input_1.png)

En los local data inputs, identifica **NiFi** y haz clic en **+ Add new**.

![image](/nifi-monitoring-splunk/assets/images/splunk/data_input_2.png)

Se desplegará una ventana como la siguiente:

![image](/nifi-monitoring-splunk/assets/images/splunk/data_input_3.jpeg)

**Te recomendamos configurar cada uno de los recursos de monitoreo de
manera independiente, para eventuales modificaciones en la configuración y
debido a los tiempos de ejecución para obtener los datos.**

Los recursos son:

- a. NiFi Endpoints
- b. NiFi Status History para Procesadores
- c. NiFi Status History para Grupos de Procesos

## 1. Configuración básica de los recursos

Para cada uno de los recursos debes configurar todos los campos requeridos:

- **NIFI Instance name**: un nombre para la instancia de NiFi.
- **NIFI API URL**: la dirección de la API REST de NiFi (ej. `http://<direccion:puerto>/nifi-api/`).
- **Auth Type**: el tipo de autenticación:
    - `none`: sin autenticación.
    - `basic`: acceso con credenciales de usuario y contraseña.
- **Interval**: tiempo en segundos entre las peticiones que extraen la
  información; 60 segundos por defecto.
- **Host**: el nombre del host de NiFi, que debe corresponder a lo definido
  en el [Lookup de Instancias](instance-lookup.es.md).
- **Index**: el índice de destino para esta fuente de datos. Se recomienda
  un índice dedicado, por ejemplo `nifi`. Si no existe, créalo primero.

### a. NiFi Endpoints

En el apartado **NIFI Endpoints**, selecciona los elementos a monitorear de
la lista:

- System Diagnostics
- Flow Status
- Site to Site

### b. NiFi Status History para Procesadores

En el apartado **NIFI Status History > List Processors ID**, indica los ID
de los procesadores a monitorear, separados por coma si son varios.

### c. NiFi Status History para Grupos de Procesos

En el apartado **NIFI Status History > Process Groups ID**, indica los ID
de los grupos de procesos a monitorear, separados por coma si son varios.

Una vez completada la configuración, haz clic en **Next** y el input queda
creado.

![image](/nifi-monitoring-splunk/assets/images/splunk/data_input_success.png)

Repite la configuración por cada recurso que necesites monitorear. Un
ejemplo de los tres recursos creados de manera independiente:

![image](/nifi-monitoring-splunk/assets/images/splunk/data_input_4.png)

Después configura el [Lookup de Instancias](instance-lookup.es.md), que es
necesario sea cual sea la estrategia.
