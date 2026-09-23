# kudaw-delivery: v1.3.0
# Manifest flavour: default/app.conf version — Splunk apps and TAs.
#
# A flavour defines exactly two functions over $MANIFEST. Everything else in the facade
# is stack-agnostic, so this file is the whole surface a new stack has to implement.

read_version() {
    local v
    v="$(grep -E '^[[:space:]]*version[[:space:]]*=' "$MANIFEST" | head -1 \
         | awk -F= '{gsub(/[[:space:]]/,"");print $2}')"
    if [[ -z "$v" ]]; then
        echo "Error: could not read version from $MANIFEST" >&2
        return 1
    fi
    printf '%s\n' "$v"
}

write_version() {
    local new="$1"
    # Un app.conf declara version en MAS DE UNA stanza — [id] y [launcher] como
    # minimo — y Splunk las quiere iguales: bumpear solo la primera deja la app
    # con metadatos inconsistentes y nada avisa. De ahi que se reemplacen todas.
    #
    # El (\r?)$ final preserva el terminador de linea. Un app.conf escrito desde
    # Windows viene con CRLF, y normalizar a LF solo la linea que se toca deja el
    # archivo mixto: ruido en el diff, y un grep del CI que esperaba \r deja de
    # encontrarlo.
    sed -i -E "s|^([[:space:]]*version[[:space:]]*=[[:space:]]*)[^\r]*(\r?)$|\\1${new}\\2|" "$MANIFEST"
}
