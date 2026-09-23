# Contribuya

Gracias por su interés en nuestro contenido, si quiere contribuir en el desarrollo de este proyecto la mejor manera de hacerlo es enviando una solicitud Pull Request bien estructurada y completa, con pruebas y documentación. Intente ser focalizado, hacer más de una cosa en una sola solicitud hará que sea más dificil de procesar.

## Cómo correr las pruebas

El add-on se genera, así que el primer paso es construirlo. No hace falta
instalar nada más: las pruebas unitarias usan solo la biblioteca estándar, y
el entorno de integración necesita Docker y nada más.

```
./tests/build-ta.sh
cd tests/unit && python3 -m unittest discover -v
```

El harness de integración levanta NiFi y Splunk en contenedores y comprueba
que los datos realmente llegan y que los campos se extraen. Cubre diez
escenarios — cada versión y arquitectura de NiFi soportada, contra las dos
formas de sacar datos de NiFi:

```
cd tests
./run.sh --list                 # los escenarios
./run.sh --list cluster         # todo sobre uno de ellos
./run.sh nifi2-current          # levantar, verificar, bajar
```

`run.sh` termina con código distinto de cero si algo falla, y baja el stack al
terminar. `--keep` lo deja corriendo para poder mirar alrededor, y `--bare`
levanta las máquinas sin instalar nada, que es la forma de ejercitar la
instalación en sí.

Un pull request no necesita la matriz completa. Corré las pruebas unitarias
más el escenario más cercano a lo que cambiaste — `./run.sh --list` dice qué
cubre cada uno. CI corre cuatro escenarios en un pull request y los diez en un
release.

Hay más detalle, incluidas las asperezas conocidas del entorno, en
[`tests/README.md`](https://github.com/kudawdev/nifi-monitoring-splunk/blob/main/tests/README.md).

## Documentación

Estas páginas son bilingües: cada `*.md` tiene su contraparte `*.es.md`, y un
cambio en una corresponde también en la otra.

## Issues

Si encontró un error o tiene una solicitud de función puede registrar un issue. Siempre recomendamos revisar los problemas creados, porque puede ser que ya haya sido reportado.
