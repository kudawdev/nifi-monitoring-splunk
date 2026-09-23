# kudaw-delivery: v1.8.0
# Shared bootstrap for the delivery scripts: locate the repo, load `delivery.conf`,
# load the manifest flavour it names.
#
# Sourced, never executed. Every script that needs to know something about THIS repo gets
# it from here, so the scripts themselves stay byte-identical across repos and the whole
# variance lives in one four-line config file.

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONF="$PROJECT_ROOT/delivery.conf"

if [[ ! -f "$CONF" ]]; then
    echo "Error: $CONF not found. This repo has the delivery facade installed but not" >&2
    echo "       configured; see resources/delivery/delivery.conf.example in tech-cicd." >&2
    exit 2
fi
# shellcheck source=/dev/null
source "$CONF"

for required in PRODUCT_LABEL PROFILE; do
    if [[ -z "${!required:-}" ]]; then
        echo "Error: $required is not set in $CONF" >&2
        exit 2
    fi
done

# A repo that ships an image owes the coordinates of that image. They used to be
# hardcoded inside each repo's docker-image.sh, which meant the registry could silently
# differ from the one the CI logged into — the value that gets copied wrong the first
# time these scripts move.
if [[ "$PROFILE" == "servicio" ]]; then
    for required in REGISTRY IMAGE_NAME; do
        if [[ -z "${!required:-}" ]]; then
            echo "Error: $required is not set in $CONF (required by the '$PROFILE' profile)" >&2
            exit 2
        fi
    done
fi

# --- which manifest are we operating on ---------------------------------------
#
# A single-artifact repo declares MANIFEST + MANIFEST_FLAVOUR, and that is the end of it.
# A monorepo declares PACKAGES instead — one line per package,
# `<name> <manifest> <flavour> [tag-prefix]` — and every version-touching command takes
# PKG= to say which one. The tag prefix defaults to `v`; `-` means this package ships
# without a git tag (its registry is the record), which `release` reports and honours.
#
# There is no default package, on purpose: in a repo that ships seven things, guessing
# which one to bump is exactly the error the facade exists to prevent. The scripts that
# need a manifest ask for it by setting NEEDS_MANIFEST=1 before sourcing this file;
# contract-check and the help footer do not, so they keep working without a PKG.
packages_names() { awk 'NF {printf "%s ", $1}' <<< "${PACKAGES:-}"; }

PKG_NAME=""
if [[ -n "${PACKAGES:-}" ]]; then
    if [[ -z "${PKG:-}" ]]; then
        if [[ -n "${NEEDS_MANIFEST:-}" ]]; then
            echo "Error: this repo declares PACKAGES, so this command needs PKG=<name>." >&2
            echo "       Available: $(packages_names)" >&2
            exit 2
        fi
        MANIFEST_REL=""
        MANIFEST=""
    else
        pkg_line="$(awk -v want="$PKG" 'NF && $1 == want {print; exit}' <<< "$PACKAGES")"
        if [[ -z "$pkg_line" ]]; then
            echo "Error: unknown package '$PKG' in $CONF. Available: $(packages_names)" >&2
            exit 2
        fi
        read -r PKG_NAME MANIFEST_REL MANIFEST_FLAVOUR PKG_TAG_PREFIX <<< "$pkg_line"
        TAG_PREFIX="${PKG_TAG_PREFIX:-v}"
    fi
else
    for required in MANIFEST MANIFEST_FLAVOUR; do
        if [[ -z "${!required:-}" ]]; then
            echo "Error: $required is not set in $CONF (nor is PACKAGES)" >&2
            exit 2
        fi
    done
    MANIFEST_REL="$MANIFEST"
    TAG_PREFIX="v"
fi

if [[ -n "$MANIFEST_REL" ]]; then
    MANIFEST="$PROJECT_ROOT/$MANIFEST_REL"
    if [[ ! -f "$MANIFEST" ]]; then
        echo "Error: manifest '$MANIFEST_REL' declared in $CONF does not exist" >&2
        exit 2
    fi
fi

if [[ -n "$MANIFEST_REL" ]]; then
FLAVOUR_FILE="$PROJECT_ROOT/scripts/manifest/${MANIFEST_FLAVOUR}.sh"
if [[ ! -f "$FLAVOUR_FILE" ]]; then
    echo "Error: unknown MANIFEST_FLAVOUR '$MANIFEST_FLAVOUR' ($FLAVOUR_FILE not found)." >&2
    echo "       Available: $(cd "$PROJECT_ROOT/scripts/manifest" 2>/dev/null \
                              && ls *.sh 2>/dev/null | sed 's/\.sh$//' | tr '\n' ' ')" >&2
    exit 2
fi
# shellcheck source=/dev/null
source "$FLAVOUR_FILE"
fi

# Where `bump` records the files POST_BUMP re-derived, for `changelog` to commit them with
# the manifest. Inside .git, not the tree: it is state between two commands, not content.
post_bump_record() { printf '%s/kudaw-delivery-post-bump\n' "$(git -C "$PROJECT_ROOT" rev-parse --absolute-git-dir)"; }

# The repo slug, derived rather than configured: a hardcoded slug is the value that gets
# copied wrong the first time these scripts move to another repo.
repo_slug() {
    local slug=""
    if command -v gh >/dev/null 2>&1; then
        slug="$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || true)"
    fi
    if [[ -z "$slug" ]]; then
        slug="$(git -C "$PROJECT_ROOT" remote get-url origin 2>/dev/null \
                | sed -E 's#^.*[:/]([^/]+/[^/]+?)(\.git)?$#\1#' || true)"
    fi
    printf '%s\n' "$slug"
}
