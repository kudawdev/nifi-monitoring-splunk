# Contribuir

Si quieres contribuir al desarrollo de este proyecto, la mejor forma es
enviar un pull request bien estructurado y completo, con pruebas y
documentación. Sé focalizado: meter más de una cosa en la misma solicitud la
hace más difícil de revisar.

## Cómo correr las pruebas

El add-on se genera, así que el primer paso es construirlo. Necesitas Docker
y Python 3, y acceso a la red la primera vez: el build instala `ucc-gen`
desde PyPI en un virtualenv propio. Las pruebas unitarias usan solo la
biblioteca estándar.

```
./tests/build-ta.sh
cd tests/unit && python3 -m unittest discover -v
```

El harness de integración levanta NiFi y Splunk en contenedores y comprueba
que los datos realmente llegan y que los campos se extraen. Cubre diez
escenarios — NiFi 1.23.2, 1.28.1, 2.0.0 y 2.11.0, standalone, multi-instancia
y cluster, repartidos entre las dos formas de sacar datos de NiFi:

```
cd tests
./run.sh --list                 # los escenarios
./run.sh --list cluster         # todo sobre uno de ellos
./run.sh nifi2-current          # levantar, verificar, bajar
```

`run.sh` termina con código distinto de cero si algo falla, y baja el stack al
terminar. `--keep` lo deja corriendo para poder mirar alrededor, y `--bare`
levanta las máquinas sin instalar nada, que es la forma de ejercitar la
instalación en sí; también las deja corriendo.

`make check` corre el lint, las pruebas unitarias, AppInspect y los
escenarios de integración en la misma imagen que usa CI; `make integration`
corre solo los escenarios.

Un pull request no necesita la matriz completa. Corre las pruebas unitarias
más el escenario más cercano a lo que cambiaste — `./run.sh --list` dice qué
cubre cada uno. CI se lanza a mano, no en cada pull request: los workflows de
dev y testing corren cuatro escenarios, y el de release los diez.

Hay más detalle, incluidas las asperezas conocidas del entorno, en
[`tests/README.md`](https://github.com/kudawdev/nifi-monitoring-splunk/blob/main/tests/README.md).

## Documentación

Estas páginas son bilingües: cada `*.md` tiene su contraparte `*.es.md`, y un
cambio en una corresponde también en la otra.

## Issues

Si encontraste un error o tienes un pedido de función, abre un issue.
Revisa primero los que ya existen -- puede que ya esté reportado.
