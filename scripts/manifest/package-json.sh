# kudaw-delivery: v1.8.0
# Manifest flavour: package.json .version — Node / bun projects.
#
# A flavour defines exactly two functions over $MANIFEST. Everything else in the facade
# is stack-agnostic, so this file is the whole surface a new stack has to implement.

read_version() {
    # jq when it is there, grep otherwise: the facade must not require a tool the repo
    # does not already depend on.
    local v=""
    if command -v jq >/dev/null 2>&1; then
        v="$(jq -r '.version // empty' "$MANIFEST" 2>/dev/null || true)"
    fi
    if [[ -z "$v" ]]; then
        v="$(grep -E '"version"[[:space:]]*:' "$MANIFEST" | head -1 \
             | sed -E 's/.*"version"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/')"
    fi
    if [[ -z "$v" ]]; then
        echo "Error: could not read version from $MANIFEST" >&2
        return 1
    fi
    printf '%s\n' "$v"
}

write_version() {
    local new="$1"
    # Rewritten in place rather than re-serialised: dumping the parsed JSON back would
    # reformat the whole manifest and bury the one-line change in noise. First match only
    # — the top-level "version" sits above `dependencies`, where the nested ones live.
    sed -i -E "0,/\"version\"[[:space:]]*:/s|(\"version\"[[:space:]]*:[[:space:]]*\")[^\"]*\"|\\1${new}\"|" "$MANIFEST"
}
