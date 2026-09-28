# kudaw-delivery: v1.8.0
# Manifest flavour: TOML [project].version — Python projects (uv / pyproject.toml).
#
# A flavour defines exactly two functions over $MANIFEST. Everything else in the facade
# is stack-agnostic, so this file is the whole surface a new stack has to implement.

read_version() {
    local v
    v="$(grep -E '^version = "' "$MANIFEST" | head -1 | sed -E 's/version = "(.+)"/\1/')"
    if [[ -z "$v" ]]; then
        echo "Error: could not read version from $MANIFEST" >&2
        return 1
    fi
    printf '%s\n' "$v"
}

write_version() {
    local new="$1"
    # Anchored + first-match-only: leaves ruff's `target-version` untouched.
    sed -i "0,/^version = \"/s|^version = \".*\"|version = \"${new}\"|" "$MANIFEST"
}
