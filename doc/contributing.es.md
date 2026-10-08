# Contribuir

Nifi Monitoring es de código abierto, bajo
[licencia MIT](https://github.com/kudawdev/nifi-monitoring-splunk/blob/main/LICENSE),
y la mantiene [Küdaw](about.es.md). Los reportes de errores, las correcciones,
los endpoints nuevos y la documentación son todos bienvenidos.

## Pull requests

Ábrelos contra `main`. El mejor pull request es uno focalizado, con pruebas y
documentación: meter más de una cosa en la misma solicitud la hace más difícil
de revisar. Antes de abrirlo:

- Corre las pruebas unitarias, y el escenario de integración más cercano a lo
  que cambiaste (más abajo).
- Si tocaste un comportamiento visible para el usuario, actualiza la
  documentación en ambos idiomas.
- Si agregaste un endpoint de NiFi, sigue la lista de
  [`AGENTS.md`](https://github.com/kudawdev/nifi-monitoring-splunk/blob/main/AGENTS.md):
  la lista de endpoints, el ruteo de sourcetype y el formulario del input van
  juntos.

Al contribuir aceptas que tu contribución queda bajo la licencia MIT, como el
resto del proyecto.

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
cubre cada uno. Cada pull request corre automáticamente el lint, las pruebas
unitarias, un build estricto de la documentación y AppInspect; los escenarios
de integración se lanzan a mano, cuatro de ellos o los diez antes de un
release.

Hay más detalle, incluidas las asperezas conocidas del entorno, en
[`tests/README.md`](https://github.com/kudawdev/nifi-monitoring-splunk/blob/main/tests/README.md).

## Documentación

Estas páginas viven en `doc/` y se construyen con MkDocs. Para previsualizarlas
mientras editas:

```
pip install -r doc/requirements.txt
mkdocs serve      # http://127.0.0.1:8000/nifi-monitoring-splunk/
```

Son bilingües: cada `*.md` tiene su contraparte `*.es.md`, y un cambio en una
corresponde también en la otra. Una página nueva va en el `nav` de
`mkdocs.yml` y en las secciones de `llmstxt`, que es como la encuentran los
agentes; las pruebas unitarias fallan si falta alguna de las tres.

## Issues

¿Encontraste un error o te falta algo? Revisa primero los
[issues existentes](https://github.com/kudawdev/nifi-monitoring-splunk/issues)
— puede que ya esté reportado — y si no,
[abre uno nuevo](https://github.com/kudawdev/nifi-monitoring-splunk/issues/new).
Un reporte de error se resuelve mucho más rápido con:

- Las versiones: de ambas apps, de NiFi y de Splunk.
- Cómo entran los datos: pull o push, y standalone, varias instancias o
  cluster.
- Qué esperabas y qué pasó en cambio — el panel, la búsqueda o el error en
  pantalla.
- En pull, el log del propio add-on:
  `index=_internal sourcetype=splunkd component=ExecProcessor "nifi.py"` alrededor del momento del problema.

Para una evaluación, una implementación o ayuda para operar las apps, escribe
a splunk.app@kudaw.com — ver [Acerca de Küdaw](about.es.md).
