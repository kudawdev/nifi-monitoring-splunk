# Adoptar `tech-cicd` v1.3.0 en un repo de apps de Splunk — lo que faltó

Para quien mantiene el skill `kudaw-tecnica:tech-cicd`. Registrado el
**2026-09-23** al adoptar la fachada en `nifi-monitoring-splunk`, perfil
`app-splunk`. La adopción funcionó; esto es lo que no estaba y lo que no
encajó.

## 1. `contract-check` aprueba una fachada que no corre

`adopt.sh` instala 12 archivos. `delivery.mk` invoca **cuatro** scripts que no
están entre ellos:

| Script | Quién debe escribirlo |
|---|---|
| `scripts/docker-image.sh` | el repo — perfil `servicio` |
| `scripts/publish.sh` | el repo — perfiles `libreria` y `app-splunk` |
| `scripts/verify.sh` | el repo — ídem |
| `scripts/version-status.sh` | **el repo, en todos los perfiles** |

Los tres primeros están documentados como responsabilidad del repo en la tabla
de «Qué queda en el repo tras adoptar». **`version-status.sh` no.** Aparece
solo en un comentario dentro de `delivery.mk` (*«the way `status` delegates to
version-status.sh»*), y `status` es un target **común a todos los perfiles**.

Lo grave no es el olvido en la tabla sino esto: **`make contract-check` pasó
igual.** Verifica los targets con `make -n`, que resuelve la receta sin
ejecutarla, así que un repo recién adoptado obtiene «OK — the surface matches
the contract» con cuatro scripts inexistentes. El fallo aparece la primera vez
que alguien corre `make status`, y el mensaje es un `No such file or
directory` que no dice de quién es el archivo.

**Sugerencias:**

- Que `contract-check` **ejecute** los targets de solo lectura (`status`,
  `version`, `baseline`, `manifest`), no solo los resuelva. Son inocuos y son
  precisamente los que se rompen así.
- Que `adopt.sh` liste, al terminar, los scripts del perfil que el repo debe
  escribir y todavía no existen — hoy solo nombra el `Makefile`.
- Que la tabla de adopción incluya `version-status.sh`.

## 2. El flavour `app-conf` supone un solo manifiesto

`app-conf.sh` lee y escribe `version` en **un** archivo. Desde que este repo
migró el TA a UCC, su `app.conf` **ya no existe en el árbol**: lo genera
`ucc-gen`. La versión vive en cuatro lugares, tres de ellos derivados:

```
nifi_monitoring/default/app.conf        ← fuente ([launcher] y [id])
nifi_TA_monitoring/globalConfig.json    ← derivado
nifi_TA_monitoring/package/app.manifest ← derivado
```

Se resolvió **de este lado**: el generador lee la versión del `app.conf` de la
app y reescribe los dos archivos del TA, y un target propio `version-sync` lo
aplica. Entre `make bump` y `make version-sync` el árbol queda inconsistente, y
un test unitario del repo lo detecta.

Funciona, pero deja una arista: **`bump` ya no basta por sí solo**, y el
contrato no tiene dónde decirlo. `PACKAGES` no sirve — trata los paquetes como
versionados de forma independiente, y acá las dos apps deben coincidir
obligatoriamente (`check-apps-version` falla si no).

**Sugerencia:** un gancho opcional en `delivery.conf`, del tipo
`POST_BUMP="make version-sync"`, que `bump` ejecute si está definido. Cualquier
repo que genere parte de su manifiesto lo va a necesitar, y con UCC eso va a
ser todos los add-ons de Splunk.

## 3. Los scripts llegan sin bit de ejecución

`adopt.sh` los escribe en modo **700**. Con `core.fileMode = false` —que este
repo tiene— git los registra como **644**, y en un clon limpio dan `permission
denied`. Es el mismo defecto que ya nos había mordido con `run.sh`.

Se corrigió acá con `git update-index --chmod=+x` y un test unitario que cubre
los once. **Sugerencia:** que `adopt.sh` los escriba 755, y que
`contract-check` verifique el modo **que git registra** (`git ls-files -s`), no
el del working copy.

## 4. Conventional Commits se asume, no se comprueba

`suggest-level` y `changelog` clasifican por prefijo. Este repo no los usa:
`suggest-level` propuso `patch` para un major, y los 66 commits del rango
cayeron en «📦 Other» — 66 asuntos no son notas de release.

No es un defecto: el contrato supone Conventional Commits y es una suposición
razonable. Pero el fallo es **silencioso y plausible**, que es la peor forma.

**Sugerencia:** que `suggest-level` informe qué porcentaje del rango pudo
clasificar, y avise cuando es bajo. Un `patch` sugerido sobre 0 % de commits
clasificados no significa lo mismo que sobre 90 %.
