# kudaw-delivery: v1.8.0
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
    # An app.conf declares version in MORE THAN ONE stanza — [id] and [launcher] at the
    # least — and Splunk wants them equal: bumping only the first leaves the app with
    # inconsistent metadata and nothing says so. Hence every occurrence.
    #
    # The trailing (\r?)$ preserves the line terminator. An app.conf written from Windows
    # is CRLF, and normalising just the touched line to LF leaves the file mixed: noise in
    # the diff, and a CI grep that expected \r stops matching.
    sed -i -E "s|^([[:space:]]*version[[:space:]]*=[[:space:]]*)[^\r]*(\r?)$|\\1${new}\\2|" "$MANIFEST"
}
