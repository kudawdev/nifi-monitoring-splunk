---
name: cicd
description: >
  Ejecuta el proceso de entrega de este repositorio: los gates, el bump de
  versión, el changelog, el empaquetado con AppInspect y el release. Úsalo
  cuando el pedido sea llevar un cambio hacia main o publicar una versión,
  aunque llegue coloquial: "liberar 2.0.0", "hacer el release", "bumpear",
  "correr los checks", "promover a main", "publicar las apps", "sacar una
  versión nueva", "está listo para liberar?". No lo uses para escribir código
  de las apps, para SPL, ni para correr el harness de integración de un
  escenario puntual (eso es tests/run.sh directo).
---

# cicd — entrega de nifi-monitoring-splunk

Perfil **app-splunk**: el entregable es un GitHub Release con los dos `.tar.gz`
adjuntos. La fachada (`Makefile` + `scripts/`, sellada por `tech-cicd`) hace lo
determinista; acá vive el juicio: cuándo parar, qué confirmar, cómo presentar
la evidencia.

**No reimplementes nada de esto.** Si una orden no está en la tabla, preguntale
a la fachada: `make help`, `make version`, `make baseline`, `make status`.

## Lo que este repo tiene de particular

Tres cosas que no se deducen de la fachada y que decidieron cómo quedó armada:

1. **La versión tiene una fuente y tres derivaciones.** `make bump` escribe
   `nifi_monitoring/default/app.conf` y para ahí. El TA no tiene `app.conf` en
   el árbol —lo genera `ucc-gen`— así que su `globalConfig.json` y su
   `package/app.manifest` salen de ahí con **`make version-sync`**. Entre el
   bump y el sync el árbol queda inconsistente y un test unitario lo grita:
   eso es correcto, no un problema. **Nunca edites la versión a mano en los
   archivos del TA.**

2. **El TA no es instalable desde el árbol.** `make build` lo genera en
   `output/`. Empaquetar `nifi_TA_monitoring/` directo produce un add-on sin
   `app.conf` y sin UI, y `slim` no se queja.

3. **El repo no usa Conventional Commits.** `make suggest-level` va a decir
   `patch` casi siempre y `make changelog` va a meter todo en «📦 Other».
   **No confíes en ninguno de los dos**: proponé el nivel leyendo los commits
   vos, y escribí la entrada del CHANGELOG a mano. La de 2.0.0 quedó así, con
   el motivo anotado arriba.

## Órdenes

| Pedido | Qué corre | Qué confirmás antes |
|---|---|---|
| `check` | `make check` | nada; es de solo lectura |
| `bump [nivel]` | `make bump LEVEL=<nivel>` y después **`make version-sync`** | el nivel, siempre — `suggest-level` no es confiable acá |
| `changelog` | editás `CHANGELOG.md` a mano, después `make changelog NO_COMMIT=1` solo si querés el andamio | el texto de la entrada |
| `package` | `make package` | nada |
| `validate` | `make validate` | nada |
| `promote` | `make promote-main` | **sí, siempre**: mergea a `main` y pushea |
| `release` | `make release` | **sí, siempre**: crea el tag y el GitHub Release |
| `status` | `make status` | nada |
| `audit` | `adopt.sh <repo> --check` desde el plugin `tech-cicd` | nada |

## La secuencia

```
check → bump → version-sync → changelog → validate → promote → release
```

Antes de empezar, verificá tres cosas que la fachada no mira:

- El árbol está limpio y estás en la rama de trabajo, no en `main`.
- `make status` no reporta un drift que no sepas explicar.
- Para un release: **la matriz de integración corrió**. `make check` corre los
  unitarios y AppInspect, no los diez escenarios. Esos son
  `cd tests && ./run.sh <perfil>` o el job `integration` de `main.yml`.

## Cómo presentar la evidencia

- Después de `check`, mostrá el resumen de AppInspect de **las dos apps** con
  sus números (`error`, `failure`, `warning`), no un "pasó". El gate es 13
  warnings y hoy son 5 y 12: un número que sube merece mirarse aunque pase.
- Después de `bump`, mostrá la versión vieja y la nueva, y **confirmá que
  `version-sync` corrió** — es el paso que se olvida.
- Antes de `promote` y de `release`, decí en una línea qué va a pasar y esperá
  el sí. Las dos son irreversibles de hecho: un push a `main` y un tag público.
- Si algo falla, mostrá la salida cruda del target. No la resumas: el mensaje
  de la fachada dice qué hacer.

## Cuando algo no encaja

No edites `delivery.mk` ni `scripts/` — están sellados. O es un valor que va en
`delivery.conf`, o es un cambio que el contrato `tech-cicd` debe absorber para
todos los repos. **Hoy hay uno abierto**: el flavour `app-conf` escribe un solo
manifiesto, y acá hacen falta tres archivos. `version-sync` lo resuelve de este
lado, pero el contrato no contempla un manifiesto repartido.
