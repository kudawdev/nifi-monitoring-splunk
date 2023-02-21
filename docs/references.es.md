# Sourcetypes

Los distintos sourcetypes utilizados por la aplicación entregan un tipo de información que corresponde:

- nifi:log:app
- nifi:log:bootstrap

Contiene el registro de todas las actividades de la aplicación NIFI,  desde la carga de archivos hasta los tiempos de ejecución o los boletines encontrados por los componentes.

- nifi:log:user

Contiene el registro de la actividad web donde interactúen los usuarios y las acciones que éstos realicen.

- nifi:api:flow_status

Dispone de la información básica relacionada al estado y el procesamiento de la aplicación NIFI 

- nifi:api:site_to_site

Entrega toda la información necesaria sobre el aplicativo para comunicarse con otras instancias.

- nifi:api:system_diagostics

Dispone de la información información de los recursos de sistema en uso y disponibles con los que cuenta la instancia de NIFI.

- nifi:reporting:task  

Corresponde a reportes internos de metricas de estado y funcionamiento del aplicativo a un nivel más detallado respecto al flow status.


- nifi:reporting:bulletin

Entrega informacion sobre los boletines internos del aplicativo donde se especifican errores ocurridos duante su funcionamiento.